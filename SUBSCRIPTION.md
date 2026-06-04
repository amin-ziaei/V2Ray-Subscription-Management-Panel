# Subscription System Documentation

This document explains how subscriptions work in the V2Ray Subscription Management Panel.

---

## Overview

A subscription link is an HTTP endpoint that returns a Base64-encoded list of proxy configurations. V2Ray-compatible clients can fetch this URL periodically and update their server list automatically.

This panel supports:

- One global subscription link
- Separate subscription links per group
- QR codes for global, group, and individual config links
- Only active configs in subscription output
- Multiple supported protocols

---

## Subscription Endpoints

### Global Subscription

```http
GET /sub
```

Returns all active configurations from all groups.

Example URL:

```text
http://your-server:8000/sub
```

### Group Subscription

```http
GET /sub/group/{group_name}
```

Returns only active configurations from a specific group.

Example URLs:

```text
http://your-server:8000/sub/group/Default
http://your-server:8000/sub/group/Germany
http://your-server:8000/sub/group/Gaming
```

If a group name contains spaces or special characters, it is URL-encoded in the generated dashboard link.

Example:

```text
Group name: Premium Servers
URL: /sub/group/Premium%20Servers
```

---

## QR Code Endpoints

### Global Subscription QR

```http
GET /qr/sub
```

Returns a PNG QR code for the global subscription URL.

### Group Subscription QR

```http
GET /qr/sub/group/{group_name}
```

Returns a PNG QR code for the group subscription URL.

### Individual Config QR

```http
GET /qr/config/{config_id}
```

Returns a PNG QR code for one config link.

---

## Output Format

The subscription response is plain text containing a Base64-encoded string.

Content-Type:

```http
text/plain
```

The decoded content is a newline-separated list of config links:

```text
vless://uuid@example.com:443?security=tls#Germany
vmess://base64payload#US
ss://method:password@example.com:8388#Singapore
```

The encoded response looks like:

```text
dmxlc3M6Ly91dWlkQGV4YW1wbGUuY29tOjQ0Mz9zZWN1cml0eT10bHMjR2VybWFueQp2bWVzczovL2Jhc2U2NHBheWxvYWQjVVMKc3M6Ly9tZXRob2Q6cGFzc3dvcmRAZXhhbXBsZS5jb206ODM4OCNTaW5nYXBvcmU=
```

---

## How the Panel Builds a Subscription

For `/sub`:

1. Read configs from SQLite
2. Keep only configs where `is_active = 1`
3. Join config links using newline separators
4. Base64 encode the joined text
5. Return the encoded result as `text/plain`

For `/sub/group/{group_name}`:

1. Decode the group name from the URL
2. Read configs where:
   - `is_active = 1`
   - `group_name = requested group`
3. Join config links using newline separators
4. Base64 encode the result
5. Return it as `text/plain`

---

## Active vs Inactive Configs

Only active configs are included in subscription output.

| Status | Included in `/sub` | Included in group subscription |
|---|---:|---:|
| Active | Yes | Yes, if group matches |
| Inactive | No | No |

This allows you to keep configs in the panel without exposing them to clients.

---

## Groups

Each config has a `group_name` field.

Groups are used for:

- Filtering configs in the dashboard
- Creating separated subscription links
- Organizing configs by location, usage, customer, or profile

Example group strategy:

| Group | Purpose |
|---|---|
| `Default` | General configs |
| `Germany` | Germany servers only |
| `Gaming` | Low-latency configs |
| `Backup` | Backup configs |
| `Mobile` | Mobile client configs |

---

## Supported Protocols

The panel accepts configs that start with one of these prefixes:

| Protocol | Prefix | Example |
|---|---|---|
| VLESS | `vless://` | `vless://uuid@example.com:443#Server` |
| VMESS | `vmess://` | `vmess://base64payload#Server` |
| Shadowsocks | `ss://` | `ss://method:password@example.com:8388#Server` |
| ShadowsocksR | `ssr://` | `ssr://base64payload` |
| Trojan | `trojan://` | `trojan://password@example.com:443#Server` |

---

## Internal Config Remark

Many config links use a remark after `#`:

```text
vless://uuid@example.com:443?security=tls#Germany-1
```

The dashboard supports editing this internal remark separately from the panel remark.

- `Panel Remark`: display name inside the web panel
- `Config Internal Remark`: the `#remark` inside the config link

If `Config Internal Remark` is left empty while saving, the `#remark` part is removed from the config link.

---

## Multi-Config Import

The add form supports multiple configs at once.

Paste one config per line:

```text
vless://uuid1@example.com:443#Germany-1
vless://uuid2@example.com:443#Germany-2
trojan://password@example.com:443#Trojan-1
```

The selected group is applied to all imported configs.

If multiple configs are inserted with one panel remark, the app appends a number to each panel remark:

```text
Germany 1
Germany 2
Germany 3
```

---

## Bulk Host/IP Replacement

The dashboard can replace the host/IP for selected configs.

Supported behavior:

| Protocol | Replacement behavior |
|---|---|
| VLESS | Replaces URL hostname |
| Trojan | Replaces URL hostname |
| Shadowsocks | Replaces URL hostname |
| VMESS | Replaces the `add` field in decoded JSON |
| SSR | Replaces host in decoded SSR payload |

This is useful when several configs share the same backend server and only the domain or IP changes.

---

## Latency Check

The dashboard supports checking config reachability.

Routes:

```http
GET /check/{config_id}
GET /check-all
```

The check performs a TCP connection attempt to the parsed `host:port`.

Stored values:

- Status
- Latency in milliseconds
- Last checked timestamp

Possible statuses:

| Status | Meaning |
|---|---|
| `Online` | TCP connection succeeded |
| `Offline` | TCP connection failed or timed out |
| `Invalid host/port` | Host or port could not be parsed |

Important note:

> This is not a full V2Ray protocol test. It only checks whether the target host and port can accept a TCP connection.

---

## Backup and Restore

Routes:

```http
GET /backup
POST /restore
```

### Backup

`GET /backup` creates and downloads a copy of the SQLite database.

Backup files are also stored under:

```text
data/backups/
```

### Restore

`POST /restore` accepts a multipart uploaded `.db` file using field name:

```text
backup_file
```

Before replacing the current database, the app automatically saves a pre-restore backup:

```text
data/backups/before-restore-YYYYMMDD-HHMMSS.db
```

---

## Client Examples

### V2RayNG

1. Open V2RayNG
2. Go to subscriptions
3. Add one of the generated URLs:
   - Global: `http://your-server:8000/sub`
   - Group: `http://your-server:8000/sub/group/Germany`
4. Refresh the subscription
5. Select a server

### Clash-style profile reference

```yaml
proxy-providers:
  my-v2ray-subscription:
    type: http
    url: "http://your-server:8000/sub"
    interval: 3600
    path: ./providers/my-v2ray-subscription.yaml
```

Compatibility depends on the client and whether it supports raw V2Ray URI subscriptions.

### Command Line Decode Test

```bash
curl http://localhost:8000/sub | base64 -d
```

Group subscription:

```bash
curl http://localhost:8000/sub/group/Default | base64 -d
```

---

## Security Notes

- Dashboard routes require HTTP Basic Authentication.
- Subscription URLs are public by design for client compatibility.
- Base64 is not encryption.
- Use HTTPS in production.
- Change the default credentials.
- Keep database backups secure because they contain full proxy configs.

---

## Troubleshooting

### The subscription is empty

Check:

- At least one config exists
- Configs are active
- You are using the correct group URL
- Group name is URL-encoded if it contains spaces

### A config does not appear in a group subscription

Check:

- The config is active
- The config has the expected group name
- The group name in the URL matches exactly

### QR code opens the wrong link

Regenerate/reload the dashboard and verify the displayed URL.

### Latency check fails

Possible causes:

- Host/port cannot be parsed
- Server is offline
- Firewall blocks the connection
- The config uses an unsupported or unusual URI format
