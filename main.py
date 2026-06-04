import base64
import json
import sqlite3
import os
import shutil
import socket
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest
import qrcode

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

# Load credentials from environment variables
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DB_PATH = Path("data/configs.db")
BACKUP_DIR = Path("data/backups")

# Authentication dependency
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_correct = compare_digest(credentials.username, ADMIN_USERNAME)
    is_password_correct = compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (is_user_correct and is_password_correct):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

# Validate V2Ray config link format
def validate_config_link(link: str) -> bool:
    protocols = ["vless://", "vmess://", "ss://", "ssr://", "trojan://"]
    return any(link.strip().startswith(proto) for proto in protocols)

def split_config_links(config_links: str) -> list[str]:
    return [line.strip() for line in config_links.splitlines() if line.strip()]

def get_config_remark(config_link: str) -> str:
    if "#" not in config_link:
        return ""
    return unquote(config_link.rsplit("#", 1)[1])

def set_config_remark(config_link: str, config_remark: str) -> str:
    base_link = config_link.rsplit("#", 1)[0]
    clean_remark = config_remark.strip()
    if not clean_remark:
        return base_link
    return f"{base_link}#{quote(clean_remark, safe='')}"

def get_config_protocol(config_link: str) -> str:
    if config_link.startswith("vless://"):
        return "VLESS"
    if config_link.startswith("vmess://"):
        return "VMESS"
    if config_link.startswith("ss://"):
        return "Shadowsocks"
    if config_link.startswith("ssr://"):
        return "SSR"
    if config_link.startswith("trojan://"):
        return "Trojan"
    return "Custom"

def decode_urlsafe_base64(value: str) -> str:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")

def encode_urlsafe_base64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")

def parse_host_port(config_link: str) -> tuple[str, int | None]:
    try:
        if config_link.startswith("vmess://"):
            payload = decode_urlsafe_base64(config_link.removeprefix("vmess://"))
            data = json.loads(payload)
            host = data.get("add") or data.get("host") or ""
            port = int(data["port"]) if str(data.get("port", "")).isdigit() else None
            return host, port

        if config_link.startswith("ssr://"):
            decoded = decode_urlsafe_base64(config_link.removeprefix("ssr://"))
            main_part = decoded.split("/?", 1)[0]
            parts = main_part.split(":")
            port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            return parts[0], port

        parsed = urlsplit(config_link)
        return parsed.hostname or "", parsed.port
    except Exception:
        return "", None

def replace_config_host(config_link: str, new_host: str) -> str:
    clean_host = new_host.strip()
    if not clean_host:
        return config_link

    if config_link.startswith("vmess://"):
        payload = decode_urlsafe_base64(config_link.removeprefix("vmess://"))
        data = json.loads(payload)
        data["add"] = clean_host
        return "vmess://" + encode_urlsafe_base64(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    if config_link.startswith("ssr://"):
        decoded = decode_urlsafe_base64(config_link.removeprefix("ssr://"))
        main_part, separator, query = decoded.partition("/?")
        parts = main_part.split(":")
        if parts:
            parts[0] = clean_host
        rebuilt = ":".join(parts) + (separator + query if separator else "")
        return "ssr://" + encode_urlsafe_base64(rebuilt)

    parsed = urlsplit(config_link)
    netloc = parsed.netloc
    userinfo = ""
    if "@" in netloc:
        userinfo, _ = netloc.rsplit("@", 1)
        userinfo += "@"
    port = f":{parsed.port}" if parsed.port else ""
    new_netloc = f"{userinfo}{clean_host}{port}"
    return urlunsplit((parsed.scheme, new_netloc, parsed.path, parsed.query, parsed.fragment))

def check_tcp_latency(config_link: str, timeout: float = 3.0) -> tuple[str, int | None]:
    host, port = parse_host_port(config_link)
    if not host or not port:
        return "Invalid host/port", None

    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((time.perf_counter() - start) * 1000)
            return "Online", latency_ms
    except Exception:
        return "Offline", None

def subscription_response(rows: list[sqlite3.Row]) -> Response:
    config_list = [row["config_link"] for row in rows if row["config_link"]]
    merged_configs = "\n".join(config_list)
    b64_encoded = base64.b64encode(merged_configs.encode("utf-8")).decode("utf-8")
    return Response(content=b64_encoded, media_type="text/plain")

def generate_qr_png(value: str) -> Response:
    if not value:
        raise HTTPException(status_code=404, detail="QR content not found")

    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")

# Initialize and connect to SQLite inside the persistent volume
def get_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v2ray_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remark TEXT NOT NULL,
            config_link TEXT NOT NULL,
            group_name TEXT NOT NULL DEFAULT 'Default',
            is_active INTEGER NOT NULL DEFAULT 1,
            last_check_status TEXT,
            last_latency_ms INTEGER,
            last_checked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("PRAGMA table_info(v2ray_configs)")
    columns = [column[1] for column in cursor.fetchall()]
    if "is_active" not in columns:
        cursor.execute("ALTER TABLE v2ray_configs ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if "group_name" not in columns:
        cursor.execute("ALTER TABLE v2ray_configs ADD COLUMN group_name TEXT NOT NULL DEFAULT 'Default'")
    if "last_check_status" not in columns:
        cursor.execute("ALTER TABLE v2ray_configs ADD COLUMN last_check_status TEXT")
    if "last_latency_ms" not in columns:
        cursor.execute("ALTER TABLE v2ray_configs ADD COLUMN last_latency_ms INTEGER")
    if "last_checked_at" not in columns:
        cursor.execute("ALTER TABLE v2ray_configs ADD COLUMN last_checked_at TIMESTAMP")
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()

# 1. Dashboard Web UI
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, username: str = Depends(verify_credentials), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM v2ray_configs ORDER BY created_at DESC")
    configs = [
        dict(config) | {
            "link_remark": get_config_remark(config["config_link"]),
            "protocol": get_config_protocol(config["config_link"]),
        }
        for config in cursor.fetchall()
    ]
    cursor.execute("SELECT DISTINCT group_name FROM v2ray_configs ORDER BY group_name COLLATE NOCASE")
    groups = [row["group_name"] for row in cursor.fetchall()]
    group_links = [
        {
            "name": group,
            "url": f"{request.base_url}sub/group/{quote(group, safe='')}",
            "qr_url": f"/qr/sub/group/{quote(group, safe='')}",
        }
        for group in groups
    ]
    stats = {
        "total": len(configs),
        "active": sum(1 for config in configs if config["is_active"]),
        "inactive": sum(1 for config in configs if not config["is_active"]),
        "groups": len(groups),
    }
    sub_url = f"{request.base_url}sub"
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "configs": configs,
            "groups": groups,
            "group_links": group_links,
            "stats": stats,
            "sub_url": sub_url,
        },
    )

# 2. Add new config route
@app.post("/add")
async def add_config(
    remark: str = Form(...),
    group_name: str = Form("Default"),
    config_link: str = Form(...),
    username: str = Depends(verify_credentials),
    db: sqlite3.Connection = Depends(get_db)
):
    config_links = split_config_links(config_link)

    if not config_links:
        raise HTTPException(status_code=400, detail="Config link cannot be empty")

    invalid_links = [link for link in config_links if not validate_config_link(link)]
    if invalid_links:
        raise HTTPException(status_code=400, detail="One or more config links have an invalid format")

    clean_remark = remark.strip()
    if not clean_remark:
        raise HTTPException(status_code=400, detail="Remark cannot be empty")
    clean_group = group_name.strip() or "Default"
    
    cursor = db.cursor()
    for index, link in enumerate(config_links, start=1):
        item_remark = clean_remark if len(config_links) == 1 else f"{clean_remark} {index}"
        cursor.execute(
            "INSERT INTO v2ray_configs (remark, config_link, group_name) VALUES (?, ?, ?)",
            (item_remark, link, clean_group),
        )
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/edit/{config_id}")
async def edit_config(
    config_id: int,
    remark: str = Form(...),
    group_name: str = Form("Default"),
    config_remark: str = Form(""),
    config_link: str = Form(...),
    username: str = Depends(verify_credentials),
    db: sqlite3.Connection = Depends(get_db)
):
    clean_remark = remark.strip()
    clean_link = set_config_remark(config_link.strip(), config_remark)

    if not clean_remark:
        raise HTTPException(status_code=400, detail="Remark cannot be empty")
    clean_group = group_name.strip() or "Default"

    if not validate_config_link(clean_link):
        raise HTTPException(status_code=400, detail="Invalid config link format")

    cursor = db.cursor()
    cursor.execute(
        "UPDATE v2ray_configs SET remark = ?, group_name = ?, config_link = ? WHERE id = ?",
        (clean_remark, clean_group, clean_link, config_id)
    )
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/bulk")
async def bulk_action(
    action: str = Form(...),
    selected_ids: list[int] = Form([]),
    bulk_group_name: str = Form("Default"),
    username: str = Depends(verify_credentials),
    db: sqlite3.Connection = Depends(get_db)
):
    if not selected_ids:
        return RedirectResponse(url="/", status_code=303)

    placeholders = ",".join("?" for _ in selected_ids)
    cursor = db.cursor()

    if action == "enable":
        cursor.execute(f"UPDATE v2ray_configs SET is_active = 1 WHERE id IN ({placeholders})", selected_ids)
    elif action == "disable":
        cursor.execute(f"UPDATE v2ray_configs SET is_active = 0 WHERE id IN ({placeholders})", selected_ids)
    elif action == "delete":
        cursor.execute(f"DELETE FROM v2ray_configs WHERE id IN ({placeholders})", selected_ids)
    elif action == "move":
        clean_group = bulk_group_name.strip() or "Default"
        cursor.execute(f"UPDATE v2ray_configs SET group_name = ? WHERE id IN ({placeholders})", [clean_group, *selected_ids])
    elif action == "replace_host":
        clean_host = bulk_group_name.strip()
        if not clean_host:
            raise HTTPException(status_code=400, detail="New host/IP cannot be empty")

        cursor.execute(f"SELECT id, config_link FROM v2ray_configs WHERE id IN ({placeholders})", selected_ids)
        rows = cursor.fetchall()
        for row in rows:
            try:
                updated_link = replace_config_host(row["config_link"], clean_host)
                cursor.execute("UPDATE v2ray_configs SET config_link = ? WHERE id = ?", (updated_link, row["id"]))
            except Exception:
                continue
    else:
        raise HTTPException(status_code=400, detail="Invalid bulk action")

    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/backup")
async def backup_database(username: str = Depends(verify_credentials)):
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"configs-{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)

    return FileResponse(
        path=backup_path,
        media_type="application/octet-stream",
        filename=backup_path.name,
    )

@app.post("/restore")
async def restore_database(
    backup_file: UploadFile = File(...),
    username: str = Depends(verify_credentials)
):
    if not backup_file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Only .db backup files are allowed")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    restore_backup = BACKUP_DIR / f"before-restore-{time.strftime('%Y%m%d-%H%M%S')}.db"
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, restore_backup)

    content = await backup_file.read()
    temp_restore_path = BACKUP_DIR / f"upload-{time.strftime('%Y%m%d-%H%M%S')}.db"
    temp_restore_path.write_bytes(content)
    try:
        test_conn = sqlite3.connect(":memory:")
        disk_conn = sqlite3.connect(temp_restore_path)
        disk_conn.backup(test_conn)
        disk_conn.close()
        test_conn.close()
    except Exception:
        temp_restore_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Invalid SQLite backup file")

    DB_PATH.write_bytes(content)
    temp_restore_path.unlink(missing_ok=True)
    return RedirectResponse(url="/", status_code=303)

@app.get("/check/{config_id}")
async def check_config_latency(config_id: int, username: str = Depends(verify_credentials), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT config_link FROM v2ray_configs WHERE id = ?", (config_id,))
    config = cursor.fetchone()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    status, latency_ms = check_tcp_latency(config["config_link"])
    cursor.execute(
        "UPDATE v2ray_configs SET last_check_status = ?, last_latency_ms = ?, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, latency_ms, config_id),
    )
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/check-all")
async def check_all_configs(username: str = Depends(verify_credentials), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, config_link FROM v2ray_configs")
    rows = cursor.fetchall()
    for row in rows:
        status, latency_ms = check_tcp_latency(row["config_link"])
        cursor.execute(
            "UPDATE v2ray_configs SET last_check_status = ?, last_latency_ms = ?, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, latency_ms, row["id"]),
        )
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/toggle/{config_id}")
async def toggle_config(config_id: int, username: str = Depends(verify_credentials), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE v2ray_configs SET is_active = CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id = ?", (config_id,))
    db.commit()
    return RedirectResponse(url="/", status_code=303)

# 3. Delete config route
@app.get("/delete/{config_id}")
async def delete_config(config_id: int, username: str = Depends(verify_credentials), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM v2ray_configs WHERE id = ?", (config_id,))
    db.commit()
    return RedirectResponse(url="/", status_code=303)

# 4. Subscription API endpoint for V2Ray clients (Base64 Encoded)
@app.get("/sub")
async def get_sub(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT config_link FROM v2ray_configs WHERE is_active = 1")
    rows = cursor.fetchall()
    return subscription_response(rows)

@app.get("/sub/group/{group_name}")
async def get_group_sub(group_name: str, db: sqlite3.Connection = Depends(get_db)):
    clean_group = unquote(group_name)
    cursor = db.cursor()
    cursor.execute(
        "SELECT config_link FROM v2ray_configs WHERE is_active = 1 AND group_name = ?",
        (clean_group,),
    )
    rows = cursor.fetchall()
    return subscription_response(rows)

@app.get("/qr/sub")
async def sub_qr(request: Request):
    return generate_qr_png(f"{request.base_url}sub")

@app.get("/qr/sub/group/{group_name}")
async def group_sub_qr(group_name: str, request: Request):
    clean_group = unquote(group_name)
    return generate_qr_png(f"{request.base_url}sub/group/{quote(clean_group, safe='')}")

@app.get("/qr/config/{config_id}")
async def config_qr(config_id: int, username: str = Depends(verify_credentials), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT config_link FROM v2ray_configs WHERE id = ?", (config_id,))
    config = cursor.fetchone()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return generate_qr_png(config["config_link"])
