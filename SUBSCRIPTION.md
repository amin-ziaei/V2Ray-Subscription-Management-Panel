# V2Ray Subscription Link Documentation

## Overview

The subscription link is a standardized format used by V2Ray clients to automatically fetch and manage multiple server configurations. This document explains how the subscription system works in this V2Ray Subscription Manager.

---

## What is a Subscription Link?

A subscription link is a URL that returns a **base64-encoded** list of V2Ray configurations. V2Ray clients (like V2RayNG, Clash, etc.) can:
- Add the subscription link once
- Automatically fetch all available server configurations
- Update configurations periodically
- Switch between servers without manual configuration

---

## Subscription Link Format

### Endpoint
```
http://your-server:8000/sub
```

### Output Format

The `/sub` endpoint returns a **base64-encoded string** containing all stored configurations.

**Example output:**
```
dmxlc3M6Ly9hYmMxMjNkZWY0NTZAZXhhbXBsZS5jb206NDQzP3BhdGg9JTJGd3Mmc2VjdXJpdHk9dGxzI0dlcm1hbnktU2VydmVyCnZtZXNzOi8vZXlBaVlXUmtJam9nSW1WNFlXMXdiR1V1WTI5dElpd2dJbllpT2lBaU1pSWdmUT09I1VTLVNlcnZlcg==
```

When decoded, it becomes:
```
vless://abc123def456@example.com:443?path=%2Fws&security=tls#Germany-Server
vmess://eyAiYWRkIjogImV4YW1wbGUuY29tIiwgInYiOiAiMiIgfQ==#US-Server
```

---

## How It Works

### Step 1: Store Configurations in Dashboard

```
1. Open http://localhost:8000
2. Log in with credentials (admin / admin123)
3. Add new configurations:
   - Remark: "Germany - Server 1"
   - Config Link: "vless://abc123def456@example.com:443?..."
4. Click "Save Configuration"
```

### Step 2: Generate Subscription URL

The application automatically:
1. **Retrieves** all stored configs from the database
2. **Merges** them with newline separators (`\n`)
3. **Encodes** the result in base64
4. **Returns** the encoded string via `/sub` endpoint

```
Database:
├─ vless://... (Germany)
├─ vmess://... (US)
└─ ss://...    (Singapore)
        ↓
    Merge with \n
        ↓
    Base64 encode
        ↓
    HTTP Response: dmxlc3M6Ly8...
```

### Step 3: V2Ray Client Processes It

```
1. Add subscription URL: http://your-server:8000/sub
2. Client fetches the base64 string
3. Client decodes it to get all configs
4. Client displays all available servers
5. User can switch between servers
6. Client periodically updates the subscription
```

---

## Supported Protocols

The subscription system supports all major V2Ray protocols:

| Protocol | Format | Example |
|----------|--------|---------|
| VLESS | `vless://` | `vless://user@host:port#remark` |
| VMESS | `vmess://` | `vmess://base64-config#remark` |
| Shadowsocks | `ss://` | `ss://method:password@host:port#remark` |
| ShadowsocksR | `ssr://` | `ssr://host:port:protocol#remark` |
| Trojan | `trojan://` | `trojan://password@host:port#remark` |

---

## API Endpoints

### 1. Get Subscription (Public)
```http
GET /sub
```

**Response:**
- Content-Type: `text/plain`
- Body: Base64-encoded configuration list

**Example:**
```bash
curl http://localhost:8000/sub
```

**Output:**
```
dmxlc3M6Ly9hYmMxMjNkZWY0NTZAZXhhbXBsZS5jb206NDQzP3BhdGg9JTJGd3Mmc2VjdXJpdHk9dGxzI0dlcm1hbnktU2VydmVyCnZtZXNzOi8vZXlBaVlXUmtJam9nSW1WNFlXMXdiR1V1WTI5dElpd2dJbllpT2lBaU1pSWdmUT09I1VTLVNlcnZlcg==
```

### 2. Dashboard (Protected)
```http
GET /
```
- Requires HTTP Basic Authentication
- Returns HTML dashboard
- Lists all stored configurations

### 3. Add Configuration (Protected)
```http
POST /add
```
- Requires HTTP Basic Authentication
- Form parameters:
  - `remark`: Server location/name (required)
  - `config_link`: Configuration link (required, must start with protocol)

**Example:**
```bash
curl -X POST http://admin:admin123@localhost:8000/add \
  -d "remark=Germany Server 1" \
  -d "config_link=vless://abc123@example.com:443#Germany"
```

### 3. Delete Configuration (Protected)
```http
GET /delete/{config_id}
```
- Requires HTTP Basic Authentication
- Deletes configuration by ID

**Example:**
```bash
curl http://admin:admin123@localhost:8000/delete/1
```

---

## Base64 Encoding/Decoding

### What is Base64?

Base64 is a binary-to-text encoding scheme. It converts binary data into ASCII string format.

**Why use it?**
- Safe transmission over HTTP/text protocols
- Compatible with all V2Ray clients
- Prevents accidental modifications
- Compresses configuration text

### Encoding Example

**Plain text (3 configs):**
```
vless://abc123@host1.com:443#Server1
vmess://def456@host2.com:10000#Server2
ss://method:pass@host3.com:8388#Server3
```

**Base64 encoded:**
```
dmxlc3M6Ly9hYmMxMjNAaG9zdDEuY29tOjQ0MyNTZXJ2ZXIxCnZtZXNzOi8vZGVmNDU2QGhvc3QyLmNvbToxMDAwMCNTZXJ2ZXIyCnNzOi8vbWV0aG9kOnBhc3NAaG9zdDMuY29tOjgzODgjU2VydmVyMw==
```

### Python Example

```python
import base64

# Encoding
configs = "vless://abc@host:443#Server1\nvmess://def@host:10000#Server2"
encoded = base64.b64encode(configs.encode()).decode()
print(encoded)
# Output: dmxlc3M6Ly9hYmNAaG9zdDo0NDMjU2VydmVyMQp2bWVzczovL2RlZkBob3N0OjEwMDAwI1NlcnZlcjI=

# Decoding
decoded = base64.b64decode(encoded).decode()
print(decoded)
# Output: vless://abc@host:443#Server1
#         vmess://def@host:10000#Server2
```

---

## How V2Ray Clients Use Subscriptions

### V2RayNG (Android/iOS)

1. Open app → "Subscription" tab
2. Tap "+" to add subscription
3. Enter subscription URL:
   ```
   http://your-server:8000/sub
   ```
4. Tap "Add"
5. Refresh to fetch configurations
6. Select a server and connect

### Clash (Windows/Mac/Linux)

1. Open Clash config
2. Add subscription profile:
   ```yaml
   - name: "My V2Ray Servers"
     type: http
     url: "http://your-server:8000/sub"
     interval: 3600
   ```
3. Update proxies
4. Select a server

### V2Ray Core (Command Line)

1. Fetch subscription:
   ```bash
   curl http://your-server:8000/sub | base64 -d
   ```

2. Add to `config.json` outbound array

---

## Security Considerations

### Public Access
- **`/sub` endpoint is publicly accessible** (by design)
- Anyone can fetch the subscription list
- Configuration links are exposed in base64 (not encrypted)

### Dashboard Protection
- Dashboard (`/`) requires HTTP Basic Authentication
- Only authenticated users can add/delete configurations
- Credentials: Set via environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD`

### Recommendations

1. **Use HTTPS** in production
   ```bash
   # Set up reverse proxy with SSL (nginx, Caddy, etc.)
   ```

2. **Change default credentials**
   ```bash
   # Edit docker-compose.yml or set environment variables
   ADMIN_USERNAME=your-username
   ADMIN_PASSWORD=your-strong-password
   ```

3. **Firewall the dashboard**
   ```bash
   # Only expose /sub endpoint publicly
   # Restrict dashboard to trusted IPs
   ```

4. **Monitor subscriptions**
   - Log who accesses `/sub`
   - Track configuration changes
   - Audit database queries

---

## Configuration Validation

The system automatically validates configuration links:

### Accepted Protocols
- ✅ `vless://`
- ✅ `vmess://`
- ✅ `ss://`
- ✅ `ssr://`
- ✅ `trojan://`

### Validation Rules
- Config link must start with one of the above protocols
- Empty remarks are rejected
- Whitespace is automatically trimmed

### Error Handling

**Invalid config attempt:**
```bash
curl -X POST http://admin:admin123@localhost:8000/add \
  -d "remark=Test" \
  -d "config_link=http://invalid.com"
  
# Response: 400 Bad Request
# Detail: "Invalid config link format. Must start with vless://, vmess://, ss://, ssr://, or trojan://"
```

---

## Troubleshooting

### Issue: V2Ray client shows "empty subscription"

**Cause:** No configurations added to dashboard

**Solution:**
1. Log in to dashboard at `http://localhost:8000`
2. Add at least one configuration
3. Refresh subscription in V2Ray client

---

### Issue: Client can't decode subscription

**Cause:** Server returned invalid base64

**Solution:**
```bash
# Test endpoint directly
curl http://localhost:8000/sub

# Verify base64 is valid
curl http://localhost:8000/sub | base64 -d
```

---

### Issue: "Invalid credentials" error

**Cause:** Wrong dashboard username/password

**Solution:**
1. Check environment variables in `docker-compose.yml`
2. Default: `admin` / `admin123`
3. Try: `curl -u admin:admin123 http://localhost:8000/`

---

### Issue: Configuration not appearing in subscription

**Cause:** Configuration stored but not returned

**Solution:**
1. Check database:
   ```bash
   docker exec v2ray_sub_panel sqlite3 data/configs.db "SELECT * FROM v2ray_configs;"
   ```
2. Verify configuration format
3. Check server logs:
   ```bash
   docker logs v2ray_sub_panel
   ```

---

## API Usage Examples

### cURL Examples

**Get subscription:**
```bash
curl http://localhost:8000/sub
```

**Add configuration:**
```bash
curl -X POST http://admin:admin123@localhost:8000/add \
  -d "remark=My Server" \
  -d "config_link=vless://user@example.com:443?path=%2Fws&security=tls#MyServer"
```

**Delete configuration:**
```bash
curl http://admin:admin123@localhost:8000/delete/1
```

**Get dashboard:**
```bash
curl -u admin:admin123 http://localhost:8000/
```

---

### Python Examples

**Fetch and decode subscription:**
```python
import requests
import base64

url = "http://localhost:8000/sub"
response = requests.get(url)

if response.status_code == 200:
    decoded = base64.b64decode(response.text).decode()
    configs = decoded.split('\n')
    for config in configs:
        print(config)
```

**Add configuration:**
```python
import requests

data = {
    "remark": "Germany Server",
    "config_link": "vless://abc123@example.com:443#Germany"
}

auth = ("admin", "admin123")
response = requests.post("http://localhost:8000/add", data=data, auth=auth)
print(response.status_code)
```

---

## Performance Notes

- Subscription list size depends on number of stored configurations
- Each configuration link is ~50-200 bytes
- Base64 encoding increases size by ~33%
- Response time: < 100ms for typical use cases

**Example:**
```
10 configurations × 150 bytes = 1.5 KB
Base64 encoded = 2 KB
Network transfer = ~2ms (on good connection)
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Format** | Base64-encoded newline-separated configs |
| **Endpoint** | `GET /sub` (public) |
| **Update** | Real-time (fetches from DB each time) |
| **Clients** | V2RayNG, Clash, V2Ray Core, etc. |
| **Speed** | ~100ms per request |
| **Security** | HTTP Basic Auth for dashboard |
| **Protocols** | VLESS, VMESS, SS, SSR, Trojan |

---

## Further Reading

- [V2Ray Official Documentation](https://www.v2fly.org/)
- [V2RayNG GitHub](https://github.com/2dust/v2rayNG)
- [Clash Documentation](https://clashofclans.github.io/)
- [Base64 Encoding](https://en.wikipedia.org/wiki/Base64)
