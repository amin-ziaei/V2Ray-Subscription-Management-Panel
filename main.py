import base64
import sqlite3
import os
import re
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

# Load credentials from environment variables
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

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

# Initialize and connect to SQLite inside the persistent volume
def get_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/configs.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v2ray_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remark TEXT NOT NULL,
            config_link TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
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
    configs = cursor.fetchall()
    sub_url = f"{request.base_url}sub"
    return templates.TemplateResponse("index.html", {"request": request, "configs": configs, "sub_url": sub_url})

# 2. Add new config route
@app.post("/add")
async def add_config(
    remark: str = Form(...),
    config_link: str = Form(...),
    username: str = Depends(verify_credentials),
    db: sqlite3.Connection = Depends(get_db)
):
    config_link = config_link.strip()
    
    if not validate_config_link(config_link):
        raise HTTPException(status_code=400, detail="Invalid config link format. Must start with vless://, vmess://, ss://, ssr://, or trojan://")
    
    if not remark.strip():
        raise HTTPException(status_code=400, detail="Remark cannot be empty")
    
    cursor = db.cursor()
    cursor.execute("INSERT INTO v2ray_configs (remark, config_link) VALUES (?, ?)", (remark.strip(), config_link))
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
    cursor.execute("SELECT config_link FROM v2ray_configs")
    rows = cursor.fetchall()
    
    config_list = [row["config_link"] for row in rows if row["config_link"]]
    merged_configs = "\n".join(config_list)
    
    b64_encoded = base64.b64encode(merged_configs.encode("utf-8")).decode("utf-8")
    return Response(content=b64_encoded, media_type="text/plain")
