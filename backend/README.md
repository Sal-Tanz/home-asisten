# ElBot Backend Core

Backend API untuk ElBot Home Asisten - Smart Home Voice Control

## Features

- ✅ Device management (CRUD)
- ✅ MQTT integration for device communication
- ✅ REST API with session-based authentication
- ✅ WebSocket support for real-time updates
- ✅ SQLite database with async operations
- ✅ Action logging for audit trail

## Requirements

- Python 3.11+
- Mosquitto MQTT broker (for production)

## Setup

1. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Generate password hash:**
```bash
python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"
```

Copy the output hash and paste it into `.env` as `APP_PASSWORD_HASH`.

## Running

**Option 1: Using uvicorn directly**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8500
```

**Option 2: Using the convenience script**
```bash
./run.sh
```

The server will start at http://localhost:8500

## API Documentation

Once running, visit:
- **Swagger UI:** http://localhost:8500/docs
- **ReDoc:** http://localhost:8500/redoc

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with password (returns session)
- `POST /api/auth/logout` - Logout (clears session)
- `GET /api/auth/status` - Check authentication status

### Devices (requires authentication)
- `GET /api/devices` - List all devices
- `POST /api/devices` - Create new device
- `GET /api/devices/{device_id}` - Get device details
- `PUT /api/devices/{device_id}` - Update device
- `DELETE /api/devices/{device_id}` - Delete device
- `POST /api/devices/{device_id}/control` - Control relay (ON/OFF/TOGGLE)
- `GET /api/devices/{device_id}/logs` - Get action logs

### Health Check
- `GET /health` - Server health and MQTT connection status

## Testing

Run all tests:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Environment Variables

See `.env.example` for all configuration options:

- `APP_PASSWORD_HASH` - Bcrypt hash of the admin password
- `SECRET_KEY` - Secret key for session encryption
- `DEBUG` - Enable debug mode (True/False)
- `DATABASE_URL` - SQLite database connection string
- `MQTT_BROKER_HOST` - MQTT broker hostname
- `MQTT_BROKER_PORT` - MQTT broker port (default: 1883)
- `MQTT_USERNAME` - MQTT username (optional)
- `MQTT_PASSWORD` - MQTT password (optional)
- `MQTT_KEEPALIVE` - MQTT keepalive interval in seconds

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings management
│   ├── auth.py              # Authentication routes
│   ├── core/
│   │   └── mqtt_service.py  # MQTT client wrapper
│   ├── db/
│   │   ├── database.py      # Database connection
│   │   └── init_db.py       # Table initialization
│   ├── devices/
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── crud.py          # Database operations
│   │   └── router.py        # API endpoints
│   └── ws/
│       └── connection_manager.py  # WebSocket manager
├── tests/                   # Test suite
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
└── README.md               # This file
```

## MQTT Topics

The backend communicates with ESP32 devices via MQTT:

- **Commands:** `elbot/{device_id}/cmd` - Send relay control commands
- **Status:** `elbot/{device_id}/status` - Receive device status updates
- **LWT:** `elbot/{device_id}/lwt` - Online/offline notifications

## Next Steps

This is Backend Core (Sub-Project 1/4). Next sub-projects:

1. **Voice Pipeline + AI Agent** - Google STT, OpenAI-compatible AI, Google TTS
2. **Web UI** - Chat interface and device management
3. **ESP32 Firmware + OTA** - Device firmware with OTA updates

## License

Private - All rights reserved
