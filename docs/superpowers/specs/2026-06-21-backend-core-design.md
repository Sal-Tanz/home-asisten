# Backend Core — ElBot Home Asisten

> **Design Document for Sub-Project 1/4**

**Goal:** Build the foundational FastAPI backend that manages devices, connects to MQTT broker, provides REST API for device CRUD, and has simple password protection — ready for Voice Pipeline and Web UI to build on top.

**Architecture:** FastAPI async server with SQLite database, MQTT service for device communication, session-based authentication, and WebSocket connection manager for future real-time features.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (async), aiosqlite, paho-mqtt (async wrapper), pydantic-settings, pytest

---

## Project Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Relay per ESP32 | 4 relay | One ESP32 controls 4 separate outputs |
| Network | LAN lokal only | Simpler security, lower latency, can add internet access later |
| Hosting | Local server (Raspberry Pi / Mini PC) | Optimal latency, same network as ESP32 |
| Authentication | Single-user with password | Simple protection without full user management |
| MQTT Security | No TLS (local only) | Simplified for local network, add TLS when going public |
| Database | SQLite async | Sufficient for single-home use, easy setup |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                 Backend Core                         │
│  ┌───────────────────────────────────────────────┐  │
│  │           FastAPI Application                 │  │
│  │  ┌─────────────┐  ┌──────────────────────┐   │  │
│  │  │   Auth      │  │   Device Router      │   │  │
│  │  │  Middleware │  │   /api/devices/*     │   │  │
│  │  └─────────────┘  └──────────────────────┘   │  │
│  │  ┌─────────────────────────────────────────┐ │  │
│  │  │      Device CRUD (crud.py)              │ │  │
│  │  └─────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────┐ │  │
│  │  │      MQTT Service (async)               │ │  │
│  │  │  - Publish commands                     │ │  │
│  │  │  - Subscribe status                     │ │  │
│  │  └─────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────┐ │  │
│  │  │   WebSocket Connection Manager          │ │  │
│  │  │   (for future real-time features)       │ │  │
│  │  └─────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │          SQLite Database                      │  │
│  │  - devices (device info + state)              │  │
│  │  - action_logs (command history)              │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                      │ MQTT pub/sub
                      ▼
          ┌───────────────────────┐
          │   Mosquitto Broker    │
          │   (local, port 1883)  │
          └───────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │   ESP32 Devices       │
          │   (4 relay each)      │
          └───────────────────────┘
```

---

## File Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, startup/shutdown, router mounting
│   ├── config.py                # Pydantic settings from .env
│   ├── auth.py                  # Session-based login/logout
│   ├── core/
│   │   ├── __init__.py
│   │   └── mqtt_service.py      # Async MQTT client wrapper
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy engine + async session
│   │   └── init_db.py           # Table creation on startup
│   ├── devices/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models: Device, ActionLog
│   │   ├── schemas.py           # Pydantic schemas for request/response
│   │   ├── crud.py              # Async CRUD functions
│   │   └── router.py            # REST API endpoints
│   └── ws/
│       ├── __init__.py
│       └── connection_manager.py # WebSocket connection tracker
├── requirements.txt
├── .env.example
├── .env                         # Git-ignored, user creates from example
└── tests/
    ├── conftest.py              # Pytest fixtures
    ├── test_auth.py             # Auth tests
    ├── test_devices.py          # Device CRUD tests
    └── test_mqtt.py             # MQTT service tests
```

---

## Database Schema

### Table: `devices`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal ID |
| device_id | TEXT | UNIQUE, NOT NULL | Used in MQTT topics (e.g., "esp32-ruang-tamu") |
| name | TEXT | NOT NULL | Display name (e.g., "Lampu Ruang Tamu") |
| room | TEXT | NOT NULL | Room name |
| type | TEXT | NOT NULL | Device type: "relay", "lampu", "sensor" |
| relay_count | INTEGER | DEFAULT 4 | Number of relays on this ESP32 |
| state | TEXT | NOT NULL | JSON string: `{"relay_1": "OFF", "relay_2": "ON", ...}` |
| is_online | BOOLEAN | DEFAULT FALSE | Updated from MQTT LWT |
| last_seen | DATETIME | | Last status message received |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | |
| updated_at | DATETIME | | Updated on state changes |

**Indexes:**
- `device_id` (unique)
- `room` (for filtering by room)

### Table: `action_logs`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| device_id | TEXT | FOREIGN KEY → devices.device_id | |
| relay | TEXT | NOT NULL | "relay_1", "relay_2", etc. |
| action | TEXT | NOT NULL | "ON", "OFF", "TOGGLE" |
| source | TEXT | NOT NULL | "manual", "voice", "automation" |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | |

**Indexes:**
- `device_id` (for querying logs per device)
- `created_at` (for time-based queries)

---

## API Endpoints

### Authentication

| Method | Path | Auth Required | Description |
|---|---|---|---|
| POST | `/api/auth/login` | No | Login with password, returns session cookie |
| POST | `/api/auth/logout` | Yes | Logout, clear session |
| GET | `/api/auth/status` | No | Check if logged in |

**Request/Response Examples:**

```json
// POST /api/auth/login
{
  "password": "your-password"
}

// Response 200
{
  "success": true,
  "message": "Login successful"
}

// Response 401
{
  "detail": "Invalid password"
}
```

### Devices

| Method | Path | Auth Required | Description |
|---|---|---|---|
| GET | `/api/devices` | Yes | List all devices |
| POST | `/api/devices` | Yes | Create new device |
| GET | `/api/devices/{device_id}` | Yes | Get device details |
| PUT | `/api/devices/{device_id}` | Yes | Update device |
| DELETE | `/api/devices/{device_id}` | Yes | Delete device |
| POST | `/api/devices/{device_id}/control` | Yes | Control relay (ON/OFF/TOGGLE) |
| GET | `/api/devices/{device_id}/logs` | Yes | Get action logs for device |

**Request/Response Examples:**

```json
// GET /api/devices
[
  {
    "id": 1,
    "device_id": "esp32-ruang-tamu",
    "name": "Lampu Ruang Tamu",
    "room": "Ruang Tamu",
    "type": "relay",
    "relay_count": 4,
    "state": {"relay_1": "ON", "relay_2": "OFF", "relay_3": "OFF", "relay_4": "OFF"},
    "is_online": true,
    "last_seen": "2026-06-21T10:30:00Z",
    "created_at": "2026-06-21T08:00:00Z",
    "updated_at": "2026-06-21T10:30:00Z"
  }
]

// POST /api/devices
{
  "device_id": "esp32-kamar-tidur",
  "name": "Lampu Kamar Tidur",
  "room": "Kamar Tidur",
  "type": "relay",
  "relay_count": 4
}

// POST /api/devices/{device_id}/control
{
  "relay": "relay_1",
  "action": "ON"
}

// Response 200
{
  "success": true,
  "device_id": "esp32-ruang-tamu",
  "relay": "relay_1",
  "new_state": "ON"
}
```

---

## MQTT Topics & Payloads

### Topic Convention

```
elbot/<device_id>/cmd          # Backend → ESP32 (commands)
elbot/<device_id>/status       # ESP32 → Backend (status updates)
elbot/<device_id>/lwt          # Last Will Testament (online/offline)
```

### Command Payload (Backend → ESP32)

```json
{
  "action": "set_state",
  "relay": "relay_1",
  "value": "ON"
}
```

### Status Payload (ESP32 → Backend)

```json
{
  "device_id": "esp32-ruang-tamu",
  "relay_1": "ON",
  "relay_2": "OFF",
  "relay_3": "OFF",
  "relay_4": "OFF",
  "rssi": -55,
  "uptime": 13452
}
```

### LWT Payload

```json
{
  "status": "offline"  // or "online"
}
```

---

## Configuration (.env)

```env
# App
APP_PASSWORD_HASH=<bcrypt-hash>
SECRET_KEY=<random-secret-for-sessions>
DEBUG=False

# Database
DATABASE_URL=sqlite+aiosqlite:///./elbot.db

# MQTT Broker
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_KEEPALIVE=60
```

**Password Hash Generation:**
```bash
python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"
```

---

## Dependencies (requirements.txt)

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
pydantic==2.9.2
pydantic-settings==2.6.1
paho-mqtt==2.1.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

---

## Testing Strategy

### Unit Tests
- `test_auth.py`: Login/logout, session validation
- `test_devices.py`: CRUD operations, validation
- `test_mqtt.py`: MQTT publish/subscribe, connection handling

### Integration Tests
- Device control → MQTT publish → verify payload
- MQTT status update → database state update
- API endpoints with authentication

### Test Fixtures (conftest.py)
- `test_client`: FastAPI TestClient
- `test_db`: In-memory SQLite database
- `mock_mqtt`: Mocked MQTT client

---

## Implementation Notes

### MQTT Service Design

Since `paho-mqtt` is not natively async, we wrap it with `asyncio.Queue`:

```python
class MQTTService:
    def __init__(self):
        self.client = mqtt.Client()
        self.message_queue = asyncio.Queue()
        
    async def publish(self, topic, payload):
        """Async wrapper for publish"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_publish, topic, payload)
    
    def _sync_publish(self, topic, payload):
        self.client.publish(topic, payload)
```

### State Management

Device state stored as JSON string in SQLite, parsed/serialized in CRUD layer:

```python
# In crud.py
device.state = json.loads(db_device.state)
```

### Session Management

Use `starlette.middleware.sessions.SessionMiddleware` with secure random key from `.env`.

---

## Success Criteria

✅ Backend starts without errors  
✅ All tests pass (pytest)  
✅ Can login with password  
✅ Can CRUD devices via REST API  
✅ Can publish MQTT commands  
✅ Can receive MQTT status updates  
✅ Database persists between restarts  
✅ Ready for Voice Pipeline integration
