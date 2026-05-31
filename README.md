# V2Ray Subscription Manager

A FastAPI-based web panel for managing V2Ray subscription configurations.

## Screenshot

![V2Ray Subscription Management Panel](sc.png)

## 🔧 Improvements Made

✅ **Fixed import error** - Corrected `fastapi.templatetools` to `fastapi.templating`

✅ **Added authentication** - Basic HTTP authentication to protect the dashboard
- Default credentials: `admin` / `admin123`
- Configure via environment variables: `ADMIN_USERNAME` and `ADMIN_PASSWORD`

✅ **Added validation** - Config links are now validated
- Supported protocols: `vless://`, `vmess://`, `ss://`, `ssr://`, `trojan://`
- Prevents invalid configurations from being saved

✅ **Improved database** - Enhanced schema with:
- Non-null `remark` field
- `created_at` timestamp for tracking configuration age
- Thread-safe database connection

✅ **Environment configuration** - Settings managed via environment variables for easier deployment

## 🚀 Quick Start

### Using Docker Compose
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials (optional)
nano .env

# Start the service
docker-compose up -d
```

Access the dashboard at `http://localhost:8000` with default credentials:
- Username: `admin`
- Password: `admin123`

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123

# Run server
uvicorn main:app --reload
```

## 📝 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_USERNAME` | admin | Dashboard username |
| `ADMIN_PASSWORD` | admin123 | Dashboard password |

**⚠️ Important:** Change default credentials in production!

## 📋 Features

- **Dashboard**: Web UI to manage V2Ray configurations
- **Add Config**: Submit new V2Ray subscription links with remarks
- **Delete Config**: Remove configurations from the subscription list
- **Subscription API** (`/sub`): Get base64-encoded subscription for V2Ray clients
- **Authentication**: Protected dashboard access
- **Data Persistence**: SQLite database stored in persistent volume

## 🔒 Security Notes

- All dashboard operations require authentication
- Use strong passwords in production
- The `/sub` endpoint is publicly accessible (by design for V2Ray clients)
- Database is persisted in the `./data` directory
