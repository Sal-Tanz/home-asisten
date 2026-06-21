# Backend Core — ElBot Home Asisten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational FastAPI backend with SQLite database, MQTT service, device CRUD API, and single-user authentication — ready for Voice Pipeline and Web UI integration.

**Architecture:** FastAPI async server with layered architecture: routers (API layer) → CRUD (business logic) → database/MQTT (infrastructure). All async for non-blocking I/O. Session-based auth for simplicity.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (async), aiosqlite, paho-mqtt, pydantic-settings, pytest

---

## File Structure Overview

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Pydantic settings
│   ├── auth.py                  # Session-based auth
│   ├── core/
│   │   ├── __init__.py
│   │   └── mqtt_service.py      # Async MQTT wrapper
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   └── init_db.py           # Table creation
│   ├── devices/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── crud.py              # CRUD functions
│   │   └── router.py            # API endpoints
│   └── ws/
│       ├── __init__.py
│       └── connection_manager.py # WebSocket manager
├── requirements.txt
├── .env.example
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_devices.py
    └── test_mqtt.py
```

---

## Task 1: Project Setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/.env`

- [ ] **Step 1: Initialize git repository**

```bash
cd /root/project/home-asisten
git init
git add .
git commit -m "chore: initial project structure"
```

- [ ] **Step 2: Create requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
pydantic==2.9.2
pydantic-settings==2.6.1
paho-mqtt==2.1.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
python-jose[cryptography]==3.3.0
itsdangerous==2.2.0

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
pytest-cov==5.0.0
```

- [ ] **Step 3: Create .env.example**

```env
# App
APP_PASSWORD_HASH=
SECRET_KEY=change-me-to-random-string
DEBUG=True

# Database
DATABASE_URL=sqlite+aiosqlite:///./elbot.db

# MQTT Broker
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_KEEPALIVE=60
```

- [ ] **Step 4: Create .env with test values**

```env
APP_PASSWORD_HASH=$2b$12$KIXZVvQ9mLqJYh5x8zYxJuOq9q8q8q8q8q8q8q8q8q8q8q8q8q8q8
SECRET_KEY=test-secret-key-for-development-only
DEBUG=True
DATABASE_URL=sqlite+aiosqlite:///./elbot.db
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_KEEPALIVE=60
```

- [ ] **Step 5: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
*.db
*.sqlite
*.sqlite3

# Testing
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 6: Install dependencies**

```bash
cd /root/project/home-asisten/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 7: Commit setup**

```bash
cd /root/project/home-asisten
git add .
git commit -m "chore: setup project with dependencies and env config"
```

---

## Task 2: Database Layer

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/database.py`
- Create: `backend/app/db/init_db.py`
- Create: `backend/app/config.py`

- [ ] **Step 1: Create config.py for settings**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_password_hash: str
    secret_key: str
    debug: bool = False
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./elbot.db"
    
    # MQTT
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_keepalive: int = 60
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Create database.py for SQLAlchemy setup**

```python
# backend/app/db/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 3: Create init_db.py for table creation**

```python
# backend/app/db/init_db.py
from app.db.database import engine, Base


async def init_db():
    """Create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 4: Create empty __init__.py files**

```python
# backend/app/__init__.py
# Empty file
```

```python
# backend/app/db/__init__.py
# Empty file
```

- [ ] **Step 5: Create test database fixture**

```python
# backend/tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a test database with tables"""
    # Use in-memory SQLite for tests
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    TestSessionLocal = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with TestSessionLocal() as session:
        yield session
    
    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()
```

- [ ] **Step 6: Create empty tests/__init__.py**

```python
# backend/tests/__init__.py
# Empty file
```

- [ ] **Step 7: Run tests to verify setup**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest --version
```

Expected: pytest version 8.3.3

- [ ] **Step 8: Commit database layer**

```bash
git add backend/app/config.py backend/app/db/ backend/tests/
git commit -m "feat: add database layer with async SQLAlchemy setup"
```

---

## Task 3: Device Models

**Files:**
- Create: `backend/app/devices/__init__.py`
- Create: `backend/app/devices/models.py`

- [ ] **Step 1: Write test for Device model**

```python
# backend/tests/test_models.py
import pytest
from datetime import datetime
from sqlalchemy import select
from app.devices.models import Device, ActionLog


@pytest.mark.asyncio
async def test_device_creation(test_db):
    """Test creating a device"""
    device = Device(
        device_id="esp32-test",
        name="Test Device",
        room="Test Room",
        type="relay",
        relay_count=4,
        state='{"relay_1": "OFF", "relay_2": "OFF", "relay_3": "OFF", "relay_4": "OFF"}',
        is_online=False,
    )
    
    test_db.add(device)
    await test_db.commit()
    await test_db.refresh(device)
    
    assert device.id is not None
    assert device.device_id == "esp32-test"
    assert device.name == "Test Device"
    assert device.room == "Test Room"
    assert device.relay_count == 4
    assert device.created_at is not None


@pytest.mark.asyncio
async def test_action_log_creation(test_db):
    """Test creating an action log"""
    # Create device first
    device = Device(
        device_id="esp32-test",
        name="Test Device",
        room="Test Room",
        type="relay",
        relay_count=4,
        state='{"relay_1": "OFF"}',
        is_online=False,
    )
    test_db.add(device)
    await test_db.commit()
    
    # Create log
    log = ActionLog(
        device_id="esp32-test",
        relay="relay_1",
        action="ON",
        source="manual",
    )
    
    test_db.add(log)
    await test_db.commit()
    await test_db.refresh(log)
    
    assert log.id is not None
    assert log.device_id == "esp32-test"
    assert log.relay == "relay_1"
    assert log.action == "ON"


@pytest.mark.asyncio
async def test_device_unique_constraint(test_db):
    """Test that device_id must be unique"""
    device1 = Device(
        device_id="esp32-test",
        name="Device 1",
        room="Room",
        type="relay",
        relay_count=4,
        state='{"relay_1": "OFF"}',
        is_online=False,
    )
    test_db.add(device1)
    await test_db.commit()
    
    device2 = Device(
        device_id="esp32-test",  # Duplicate
        name="Device 2",
        room="Room",
        type="relay",
        relay_count=4,
        state='{"relay_1": "OFF"}',
        is_online=False,
    )
    test_db.add(device2)
    
    with pytest.raises(Exception):  # IntegrityError
        await test_db.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_models.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.devices.models'"

- [ ] **Step 3: Create devices __init__.py**

```python
# backend/app/devices/__init__.py
# Empty file
```

- [ ] **Step 4: Create Device and ActionLog models**

```python
# backend/app/devices/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from app.db.database import Base


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    room = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    relay_count = Column(Integer, default=4, nullable=False)
    state = Column(Text, nullable=False)  # JSON string
    is_online = Column(Boolean, default=False, nullable=False)
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Device(device_id='{self.device_id}', name='{self.name}')>"


class ActionLog(Base):
    __tablename__ = "action_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, nullable=False, index=True)
    relay = Column(String, nullable=False)
    action = Column(String, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index("idx_device_created", "device_id", "created_at"),
    )
    
    def __repr__(self):
        return f"<ActionLog(device_id='{self.device_id}', action='{self.action}')>"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_models.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit models**

```bash
git add backend/app/devices/ backend/tests/test_models.py
git commit -m "feat: add Device and ActionLog SQLAlchemy models"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `backend/app/devices/schemas.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write test for schemas**

```python
# backend/tests/test_schemas.py
import pytest
from app.devices.schemas import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceControlRequest,
)


def test_device_create_valid():
    """Test valid device creation schema"""
    data = {
        "device_id": "esp32-test",
        "name": "Test Device",
        "room": "Test Room",
        "type": "relay",
        "relay_count": 4,
    }
    
    schema = DeviceCreate(**data)
    assert schema.device_id == "esp32-test"
    assert schema.name == "Test Device"
    assert schema.relay_count == 4


def test_device_create_default_relay_count():
    """Test default relay count"""
    data = {
        "device_id": "esp32-test",
        "name": "Test Device",
        "room": "Test Room",
        "type": "relay",
    }
    
    schema = DeviceCreate(**data)
    assert schema.relay_count == 4  # Default


def test_device_create_invalid_device_id():
    """Test device_id validation"""
    data = {
        "device_id": "invalid device id",  # Spaces not allowed
        "name": "Test Device",
        "room": "Test Room",
        "type": "relay",
    }
    
    with pytest.raises(Exception):  # ValidationError
        DeviceCreate(**data)


def test_device_control_request():
    """Test device control request schema"""
    data = {
        "relay": "relay_1",
        "action": "ON",
    }
    
    schema = DeviceControlRequest(**data)
    assert schema.relay == "relay_1"
    assert schema.action == "ON"


def test_device_control_invalid_action():
    """Test invalid action in control request"""
    data = {
        "relay": "relay_1",
        "action": "INVALID",  # Not ON/OFF/TOGGLE
    }
    
    with pytest.raises(Exception):  # ValidationError
        DeviceControlRequest(**data)


def test_device_response():
    """Test device response schema"""
    data = {
        "id": 1,
        "device_id": "esp32-test",
        "name": "Test Device",
        "room": "Test Room",
        "type": "relay",
        "relay_count": 4,
        "state": {"relay_1": "ON", "relay_2": "OFF"},
        "is_online": True,
        "created_at": "2026-06-21T10:00:00",
        "updated_at": "2026-06-21T10:00:00",
    }
    
    schema = DeviceResponse(**data)
    assert schema.id == 1
    assert schema.state["relay_1"] == "ON"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_schemas.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.devices.schemas'"

- [ ] **Step 3: Create schemas.py**

```python
# backend/app/devices/schemas.py
import re
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator


class DeviceCreate(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    room: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    relay_count: int = Field(default=4, ge=1, le=16)
    
    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, v: str) -> str:
        # Only allow alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("device_id must contain only letters, numbers, hyphens, and underscores")
        return v
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = ["relay", "lampu", "sensor"]
        if v not in allowed:
            raise ValueError(f"type must be one of: {allowed}")
        return v


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    room: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = None
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = ["relay", "lampu", "sensor"]
            if v not in allowed:
                raise ValueError(f"type must be one of: {allowed}")
        return v


class DeviceControlRequest(BaseModel):
    relay: str = Field(..., pattern=r"^relay_\d+$")
    action: str = Field(..., pattern=r"^(ON|OFF|TOGGLE)$")


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    name: str
    room: str
    type: str
    relay_count: int
    state: Dict[str, str]
    is_online: bool
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_schemas.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit schemas**

```bash
git add backend/app/devices/schemas.py backend/tests/test_schemas.py
git commit -m "feat: add Pydantic schemas for device validation"
```

---

## Task 5: Device CRUD Functions

**Files:**
- Create: `backend/app/devices/crud.py`
- Test: `backend/tests/test_devices.py`

- [ ] **Step 1: Write test for CRUD functions**

```python
# backend/tests/test_devices.py
import pytest
import json
from sqlalchemy import select
from app.devices.models import Device, ActionLog
from app.devices.crud import (
    create_device,
    get_device,
    get_devices,
    update_device,
    delete_device,
    update_device_state,
    create_action_log,
    get_device_logs,
)
from app.devices.schemas import DeviceCreate, DeviceUpdate, DeviceControlRequest


@pytest.mark.asyncio
async def test_create_device(test_db):
    """Test creating a device"""
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Test Device",
        room="Test Room",
        type="relay",
        relay_count=4,
    )
    
    device = await create_device(test_db, device_data)
    
    assert device.id is not None
    assert device.device_id == "esp32-test"
    assert device.state == '{"relay_1": "OFF", "relay_2": "OFF", "relay_3": "OFF", "relay_4": "OFF"}'


@pytest.mark.asyncio
async def test_get_device(test_db):
    """Test getting a device by device_id"""
    # Create device
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Test Device",
        room="Test Room",
        type="relay",
    )
    await create_device(test_db, device_data)
    
    # Get device
    device = await get_device(test_db, "esp32-test")
    
    assert device is not None
    assert device.device_id == "esp32-test"


@pytest.mark.asyncio
async def test_get_device_not_found(test_db):
    """Test getting non-existent device"""
    device = await get_device(test_db, "non-existent")
    assert device is None


@pytest.mark.asyncio
async def test_get_devices(test_db):
    """Test getting all devices"""
    # Create multiple devices
    for i in range(3):
        device_data = DeviceCreate(
            device_id=f"esp32-{i}",
            name=f"Device {i}",
            room="Room",
            type="relay",
        )
        await create_device(test_db, device_data)
    
    devices = await get_devices(test_db)
    
    assert len(devices) == 3


@pytest.mark.asyncio
async def test_update_device(test_db):
    """Test updating a device"""
    # Create device
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Old Name",
        room="Old Room",
        type="relay",
    )
    await create_device(test_db, device_data)
    
    # Update device
    update_data = DeviceUpdate(name="New Name", room="New Room")
    device = await update_device(test_db, "esp32-test", update_data)
    
    assert device.name == "New Name"
    assert device.room == "New Room"


@pytest.mark.asyncio
async def test_delete_device(test_db):
    """Test deleting a device"""
    # Create device
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Test Device",
        room="Room",
        type="relay",
    )
    await create_device(test_db, device_data)
    
    # Delete device
    deleted = await delete_device(test_db, "esp32-test")
    
    assert deleted is True
    
    # Verify deleted
    device = await get_device(test_db, "esp32-test")
    assert device is None


@pytest.mark.asyncio
async def test_update_device_state(test_db):
    """Test updating device state"""
    # Create device
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Test Device",
        room="Room",
        type="relay",
    )
    await create_device(test_db, device_data)
    
    # Update state
    new_state = {"relay_1": "ON", "relay_2": "OFF", "relay_3": "OFF", "relay_4": "OFF"}
    device = await update_device_state(test_db, "esp32-test", new_state)
    
    assert json.loads(device.state)["relay_1"] == "ON"


@pytest.mark.asyncio
async def test_create_action_log(test_db):
    """Test creating an action log"""
    # Create device
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Test Device",
        room="Room",
        type="relay",
    )
    await create_device(test_db, device_data)
    
    # Create log
    log = await create_action_log(
        test_db,
        device_id="esp32-test",
        relay="relay_1",
        action="ON",
        source="manual",
    )
    
    assert log.id is not None
    assert log.action == "ON"


@pytest.mark.asyncio
async def test_get_device_logs(test_db):
    """Test getting action logs for a device"""
    # Create device
    device_data = DeviceCreate(
        device_id="esp32-test",
        name="Test Device",
        room="Room",
        type="relay",
    )
    await create_device(test_db, device_data)
    
    # Create multiple logs
    for action in ["ON", "OFF", "ON"]:
        await create_action_log(
            test_db,
            device_id="esp32-test",
            relay="relay_1",
            action=action,
            source="manual",
        )
    
    logs = await get_device_logs(test_db, "esp32-test", limit=10)
    
    assert len(logs) == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_devices.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.devices.crud'"

- [ ] **Step 3: Create crud.py**

```python
# backend/app/devices/crud.py
import json
from typing import List, Optional
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.devices.models import Device, ActionLog
from app.devices.schemas import DeviceCreate, DeviceUpdate


async def create_device(db: AsyncSession, device_data: DeviceCreate) -> Device:
    """Create a new device"""
    # Initialize state with all relays OFF
    initial_state = {f"relay_{i}": "OFF" for i in range(1, device_data.relay_count + 1)}
    
    device = Device(
        device_id=device_data.device_id,
        name=device_data.name,
        room=device_data.room,
        type=device_data.type,
        relay_count=device_data.relay_count,
        state=json.dumps(initial_state),
        is_online=False,
    )
    
    db.add(device)
    await db.commit()
    await db.refresh(device)
    
    return device


async def get_device(db: AsyncSession, device_id: str) -> Optional[Device]:
    """Get a device by device_id"""
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    return result.scalar_one_or_none()


async def get_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Device]:
    """Get all devices"""
    result = await db.execute(select(Device).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_device(
    db: AsyncSession, device_id: str, device_data: DeviceUpdate
) -> Optional[Device]:
    """Update a device"""
    device = await get_device(db, device_id)
    
    if not device:
        return None
    
    update_data = device_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(device, key, value)
    
    await db.commit()
    await db.refresh(device)
    
    return device


async def delete_device(db: AsyncSession, device_id: str) -> bool:
    """Delete a device"""
    device = await get_device(db, device_id)
    
    if not device:
        return False
    
    await db.delete(device)
    await db.commit()
    
    return True


async def update_device_state(
    db: AsyncSession, device_id: str, new_state: dict
) -> Optional[Device]:
    """Update device state (called when MQTT status received)"""
    device = await get_device(db, device_id)
    
    if not device:
        return None
    
    device.state = json.dumps(new_state)
    await db.commit()
    await db.refresh(device)
    
    return device


async def create_action_log(
    db: AsyncSession,
    device_id: str,
    relay: str,
    action: str,
    source: str,
) -> ActionLog:
    """Create an action log entry"""
    log = ActionLog(
        device_id=device_id,
        relay=relay,
        action=action,
        source=source,
    )
    
    db.add(log)
    await db.commit()
    await db.refresh(log)
    
    return log


async def get_device_logs(
    db: AsyncSession, device_id: str, skip: int = 0, limit: int = 100
) -> List[ActionLog]:
    """Get action logs for a device"""
    result = await db.execute(
        select(ActionLog)
        .where(ActionLog.device_id == device_id)
        .order_by(ActionLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_devices.py -v
```

Expected: 9 passed

- [ ] **Step 5: Commit CRUD functions**

```bash
git add backend/app/devices/crud.py backend/tests/test_devices.py
git commit -m "feat: add device CRUD functions with async database operations"
```

---

## Task 6: MQTT Service

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/mqtt_service.py`
- Test: `backend/tests/test_mqtt.py`

- [ ] **Step 1: Write test for MQTT service**

```python
# backend/tests/test_mqtt.py
import pytest
import json
from unittest.mock import Mock, MagicMock, AsyncMock
from app.core.mqtt_service import MQTTService


@pytest.fixture
def mqtt_service():
    """Create MQTT service instance"""
    service = MQTTService(
        broker_host="localhost",
        broker_port=1883,
        username="",
        password="",
    )
    return service


def test_mqtt_service_initialization(mqtt_service):
    """Test MQTT service initialization"""
    assert mqtt_service.broker_host == "localhost"
    assert mqtt_service.broker_port == 1883
    assert mqtt_service.client is not None


@pytest.mark.asyncio
async def test_mqtt_publish_command(mqtt_service):
    """Test publishing a command to device"""
    # Mock the client
    mqtt_service.client.publish = Mock()
    mqtt_service._connected = True
    
    await mqtt_service.publish_command(
        device_id="esp32-test",
        relay="relay_1",
        action="ON",
    )
    
    # Verify publish was called with correct topic and payload
    mqtt_service.client.publish.assert_called_once()
    call_args = mqtt_service.client.publish.call_args
    
    topic = call_args[0][0]
    payload = json.loads(call_args[0][1])
    
    assert topic == "elbot/esp32-test/cmd"
    assert payload["action"] == "set_state"
    assert payload["relay"] == "relay_1"
    assert payload["value"] == "ON"


@pytest.mark.asyncio
async def test_mqtt_subscribe_status(mqtt_service):
    """Test subscribing to status updates"""
    mqtt_service.client.subscribe = Mock()
    mqtt_service._connected = True
    
    await mqtt_service.subscribe_status()
    
    # Should subscribe to wildcard topic for all devices
    mqtt_service.client.subscribe.assert_called_once_with("elbot/+/status")


@pytest.mark.asyncio
async def test_mqtt_subscribe_lwt(mqtt_service):
    """Test subscribing to LWT (online/offline) messages"""
    mqtt_service.client.subscribe = Mock()
    mqtt_service._connected = True
    
    await mqtt_service.subscribe_lwt()
    
    # Should subscribe to wildcard topic for all devices
    mqtt_service.client.subscribe.assert_called_once_with("elbot/+/lwt")


def test_mqtt_message_handler(mqtt_service):
    """Test message handler processes status updates"""
    # Mock callback
    callback = AsyncMock()
    mqtt_service.on_status_message = callback
    
    # Simulate incoming message
    msg = Mock()
    msg.topic = "elbot/esp32-test/status"
    msg.payload = json.dumps({
        "device_id": "esp32-test",
        "relay_1": "ON",
        "relay_2": "OFF",
    }).encode()
    
    mqtt_service._on_message(None, None, msg)
    
    # Verify message was queued
    assert not mqtt_service.message_queue.empty()


@pytest.mark.asyncio
async def test_mqtt_connection_handling(mqtt_service):
    """Test connection state management"""
    # Initially not connected
    assert mqtt_service._connected is False
    
    # Simulate connection
    mqtt_service._on_connect(None, None, None, 0)
    assert mqtt_service._connected is True
    
    # Simulate disconnect
    mqtt_service._on_disconnect(None, None, 0)
    assert mqtt_service._connected is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_mqtt.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.mqtt_service'"

- [ ] **Step 3: Create core __init__.py**

```python
# backend/app/core/__init__.py
# Empty file
```

- [ ] **Step 4: Create mqtt_service.py**

```python
# backend/app/core/mqtt_service.py
import asyncio
import json
import logging
from typing import Optional, Callable, Any
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        username: str = "",
        password: str = "",
        keepalive: int = 60,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.keepalive = keepalive
        
        self.client = mqtt.Client()
        self._connected = False
        
        # Message queue for async processing
        self.message_queue = asyncio.Queue()
        
        # Callback for status messages
        self.on_status_message: Optional[Callable] = None
        self.on_lwt_message: Optional[Callable] = None
        
        # Setup credentials if provided
        if username:
            self.client.username_pw_set(username, password)
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self._connected = True
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
            self._connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        logger.warning(f"Disconnected from MQTT broker, return code {rc}")
        self._connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            logger.debug(f"Received MQTT message: {topic} - {payload}")
            
            # Queue message for async processing
            asyncio.run_coroutine_threadsafe(
                self.message_queue.put((topic, payload)),
                asyncio.get_event_loop()
            )
            
            # Route to appropriate handler
            if "/status" in topic:
                if self.on_status_message:
                    asyncio.run_coroutine_threadsafe(
                        self.on_status_message(topic, payload),
                        asyncio.get_event_loop()
                    )
            elif "/lwt" in topic:
                if self.on_lwt_message:
                    asyncio.run_coroutine_threadsafe(
                        self.on_lwt_message(topic, payload),
                        asyncio.get_event_loop()
                    )
        
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    async def connect(self):
        """Connect to MQTT broker"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.connect(self.broker_host, self.broker_port, self.keepalive)
        )
        # Start the loop in a separate thread
        self.client.loop_start()
        logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
    
    async def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.disconnect)
        logger.info("Disconnected from MQTT broker")
    
    async def publish_command(
        self,
        device_id: str,
        relay: str,
        action: str,
    ):
        """Publish a command to a device"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot publish command")
            return
        
        topic = f"elbot/{device_id}/cmd"
        payload = {
            "action": "set_state",
            "relay": relay,
            "value": action,
        }
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.publish(topic, json.dumps(payload), qos=1)
        )
        
        logger.info(f"Published command to {topic}: {payload}")
    
    async def subscribe_status(self):
        """Subscribe to status updates from all devices"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot subscribe")
            return
        
        topic = "elbot/+/status"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.client.subscribe(topic))
        
        logger.info(f"Subscribed to {topic}")
    
    async def subscribe_lwt(self):
        """Subscribe to LWT (online/offline) messages from all devices"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot subscribe")
            return
        
        topic = "elbot/+/lwt"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.client.subscribe(topic))
        
        logger.info(f"Subscribed to {topic}")
    
    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self._connected
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_mqtt.py -v
```

Expected: 6 passed

- [ ] **Step 6: Commit MQTT service**

```bash
git add backend/app/core/ backend/tests/test_mqtt.py
git commit -m "feat: add async MQTT service wrapper for device communication"
```

---

## Task 7: FastAPI Application Setup

**Files:**
- Create: `backend/app/main.py`
- Modify: `backend/app/db/database.py` (add dependency override for tests)

- [ ] **Step 1: Write test for app startup**

```python
# backend/tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db, AsyncSessionLocal


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_app_root(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ElBot Backend API", "version": "1.0.0"}


@pytest.mark.asyncio
async def test_app_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "healthy"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_main.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.main'"

- [ ] **Step 3: Create main.py**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.db.init_db import init_db
from app.core.mqtt_service import MQTTService
from app.devices.router import router as devices_router

settings = get_settings()

# Global MQTT service instance
mqtt_service: MQTTService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global mqtt_service
    
    # Startup
    await init_db()
    
    # Initialize MQTT service
    mqtt_service = MQTTService(
        broker_host=settings.mqtt_broker_host,
        broker_port=settings.mqtt_broker_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        keepalive=settings.mqtt_keepalive,
    )
    
    # Store in app state for access in routes
    app.state.mqtt_service = mqtt_service
    
    # Connect to MQTT broker (non-blocking, will retry if fails)
    try:
        await mqtt_service.connect()
        await mqtt_service.subscribe_status()
        await mqtt_service.subscribe_lwt()
    except Exception as e:
        print(f"Warning: Could not connect to MQTT broker: {e}")
    
    yield
    
    # Shutdown
    if mqtt_service:
        await mqtt_service.disconnect()


app = FastAPI(
    title="ElBot Backend API",
    description="Backend for ElBot Home Asisten - Smart Home Voice Control",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "ElBot Backend API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    mqtt_connected = mqtt_service.is_connected() if mqtt_service else False
    
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_connected,
    }


def get_mqtt_service() -> MQTTService:
    """Dependency for getting MQTT service"""
    return mqtt_service
```

- [ ] **Step 4: Create empty device router (placeholder)**

```python
# backend/app/devices/router.py
from fastapi import APIRouter

router = APIRouter()

# Endpoints will be added in next tasks
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_main.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit app setup**

```bash
git add backend/app/main.py backend/app/devices/router.py backend/tests/test_main.py
git commit -m "feat: add FastAPI application with lifespan and health check"
```

---

## Task 8: Device REST API Endpoints

**Files:**
- Modify: `backend/app/devices/router.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write test for API endpoints**

```python
# backend/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.db.database import get_db
from app.devices.models import Device


@pytest.fixture
def client(test_db: AsyncSession):
    """Create test client with test database"""
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_device_api(client):
    """Test POST /api/devices"""
    response = client.post(
        "/api/devices",
        json={
            "device_id": "esp32-test",
            "name": "Test Device",
            "room": "Test Room",
            "type": "relay",
            "relay_count": 4,
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "esp32-test"
    assert data["name"] == "Test Device"
    assert data["relay_count"] == 4


@pytest.mark.asyncio
async def test_create_device_duplicate(client):
    """Test creating device with duplicate device_id"""
    # Create first device
    client.post(
        "/api/devices",
        json={
            "device_id": "esp32-test",
            "name": "Device 1",
            "room": "Room",
            "type": "relay",
        },
    )
    
    # Try to create duplicate
    response = client.post(
        "/api/devices",
        json={
            "device_id": "esp32-test",
            "name": "Device 2",
            "room": "Room",
            "type": "relay",
        },
    )
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_devices_api(client):
    """Test GET /api/devices"""
    # Create devices
    for i in range(3):
        client.post(
            "/api/devices",
            json={
                "device_id": f"esp32-{i}",
                "name": f"Device {i}",
                "room": "Room",
                "type": "relay",
            },
        )
    
    response = client.get("/api/devices")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_get_device_api(client):
    """Test GET /api/devices/{device_id}"""
    # Create device
    client.post(
        "/api/devices",
        json={
            "device_id": "esp32-test",
            "name": "Test Device",
            "room": "Room",
            "type": "relay",
        },
    )
    
    response = client.get("/api/devices/esp32-test")
    
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "esp32-test"


@pytest.mark.asyncio
async def test_get_device_not_found_api(client):
    """Test GET /api/devices/{device_id} when device doesn't exist"""
    response = client.get("/api/devices/non-existent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_device_api(client):
    """Test PUT /api/devices/{device_id}"""
    # Create device
    client.post(
        "/api/devices",
        json={
            "device_id": "esp32-test",
            "name": "Old Name",
            "room": "Old Room",
            "type": "relay",
        },
    )
    
    # Update device
    response = client.put(
        "/api/devices/esp32-test",
        json={
            "name": "New Name",
            "room": "New Room",
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["room"] == "New Room"


@pytest.mark.asyncio
async def test_delete_device_api(client):
    """Test DELETE /api/devices/{device_id}"""
    # Create device
    client.post(
        "/api/devices",
        json={
            "device_id": "esp32-test",
            "name": "Test Device",
            "room": "Room",
            "type": "relay",
        },
    )
    
    # Delete device
    response = client.delete("/api/devices/esp32-test")
    
    assert response.status_code == 200
    
    # Verify deleted
    response = client.get("/api/devices/esp32-test")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_api.py -v
```

Expected: FAIL with endpoints not implemented

- [ ] **Step 3: Implement device router endpoints**

```python
# backend/app/devices/router.py
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.devices.crud import (
    create_device,
    get_device,
    get_devices,
    update_device,
    delete_device,
    update_device_state,
    create_action_log,
    get_device_logs,
)
from app.devices.schemas import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceControlRequest,
)
from app.main import get_mqtt_service

router = APIRouter(tags=["devices"])


@router.post("/devices", response_model=DeviceResponse)
async def create_device_endpoint(
    device_data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new device"""
    # Check if device already exists
    existing = await get_device(db, device_data.device_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Device with device_id '{device_data.device_id}' already exists",
        )
    
    device = await create_device(db, device_data)
    
    # Convert state from JSON string to dict for response
    response_data = DeviceResponse.model_validate(device)
    response_data.state = json.loads(device.state)
    
    return response_data


@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get all devices"""
    devices = await get_devices(db, skip=skip, limit=limit)
    
    # Convert state from JSON string to dict for response
    result = []
    for device in devices:
        response_data = DeviceResponse.model_validate(device)
        response_data.state = json.loads(device.state)
        result.append(response_data)
    
    return result


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device_endpoint(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific device"""
    device = await get_device(db, device_id)
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    response_data = DeviceResponse.model_validate(device)
    response_data.state = json.loads(device.state)
    
    return response_data


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device_endpoint(
    device_id: str,
    device_data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a device"""
    device = await update_device(db, device_id, device_data)
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    response_data = DeviceResponse.model_validate(device)
    response_data.state = json.loads(device.state)
    
    return response_data


@router.delete("/devices/{device_id}")
async def delete_device_endpoint(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a device"""
    deleted = await delete_device(db, device_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {"message": "Device deleted successfully"}


@router.post("/devices/{device_id}/control")
async def control_device_endpoint(
    device_id: str,
    control_data: DeviceControlRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Control a device (send command via MQTT)"""
    # Get device
    device = await get_device(db, device_id)
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Get MQTT service
    mqtt_service = request.app.state.mqtt_service
    
    if not mqtt_service or not mqtt_service.is_connected():
        raise HTTPException(
            status_code=503,
            detail="MQTT broker not connected",
        )
    
    # Calculate new state if TOGGLE
    action = control_data.action
    if action == "TOGGLE":
        current_state = json.loads(device.state)
        current_value = current_state.get(control_data.relay, "OFF")
        action = "OFF" if current_value == "ON" else "ON"
    
    # Publish command via MQTT
    await mqtt_service.publish_command(
        device_id=device_id,
        relay=control_data.relay,
        action=action,
    )
    
    # Update device state
    current_state = json.loads(device.state)
    current_state[control_data.relay] = action
    await update_device_state(db, device_id, current_state)
    
    # Log action
    await create_action_log(
        db,
        device_id=device_id,
        relay=control_data.relay,
        action=action,
        source="manual",
    )
    
    return {
        "success": True,
        "device_id": device_id,
        "relay": control_data.relay,
        "new_state": action,
    }


@router.get("/devices/{device_id}/logs")
async def get_device_logs_endpoint(
    device_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get action logs for a device"""
    device = await get_device(db, device_id)
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    logs = await get_device_logs(db, device_id, skip=skip, limit=limit)
    
    return logs
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_api.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit API endpoints**

```bash
git add backend/app/devices/router.py backend/tests/test_api.py
git commit -m "feat: add device REST API endpoints with CRUD integration"
```

---

## Task 9: Authentication

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write test for authentication**

```python
# backend/tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from passlib.hash import bcrypt
from app.main import app
from app.config import get_settings


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_password():
    """Set test password"""
    settings = get_settings()
    settings.app_password_hash = bcrypt.hash("test123")
    return "test123"


@pytest.mark.asyncio
async def test_login_success(client, test_password):
    """Test successful login"""
    response = client.post(
        "/api/auth/login",
        json={"password": "test123"},
    )
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "session" in response.cookies


@pytest.mark.asyncio
async def test_login_failure(client, test_password):
    """Test login with wrong password"""
    response = client.post(
        "/api/auth/login",
        json={"password": "wrong"},
    )
    
    assert response.status_code == 401
    assert "Invalid password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout(client, test_password):
    """Test logout"""
    # Login first
    client.post(
        "/api/auth/login",
        json={"password": "test123"},
    )
    
    # Logout
    response = client.post("/api/auth/logout")
    
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_auth_status_authenticated(client, test_password):
    """Test auth status when authenticated"""
    # Login first
    client.post(
        "/api/auth/login",
        json={"password": "test123"},
    )
    
    response = client.get("/api/auth/status")
    
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


@pytest.mark.asyncio
async def test_auth_status_not_authenticated(client):
    """Test auth status when not authenticated"""
    response = client.get("/api/auth/status")
    
    assert response.status_code == 200
    assert response.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    """Test that protected endpoints require authentication"""
    response = client.get("/api/devices")
    
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_auth.py -v
```

Expected: FAIL with auth endpoints not implemented

- [ ] **Step 3: Create auth.py**

```python
# backend/app/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from passlib.hash import bcrypt
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


class LoginRequest(BaseModel):
    password: str


def verify_password(plain_password: str) -> bool:
    """Verify password against stored hash"""
    return bcrypt.verify(plain_password, settings.app_password_hash)


def get_current_user(request: Request) -> bool:
    """Dependency to check if user is authenticated"""
    session = request.session
    if not session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
):
    """Login with password"""
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Set session
    response.session = {"authenticated": True}
    
    return JSONResponse(
        content={"success": True, "message": "Login successful"},
        headers={"Set-Cookie": response.headers.get("Set-Cookie", "")}
    )


@router.post("/logout", dependencies=[Depends(get_current_user)])
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    response.session = {}
    
    return {"success": True, "message": "Logout successful"}


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status"""
    authenticated = request.session.get("authenticated", False)
    
    return {"authenticated": authenticated}
```

- [ ] **Step 4: Update main.py to include auth router and session middleware**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.config import get_settings
from app.db.init_db import init_db
from app.core.mqtt_service import MQTTService
from app.devices.router import router as devices_router
from app.auth import router as auth_router, get_current_user

settings = get_settings()

# Global MQTT service instance
mqtt_service: MQTTService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global mqtt_service
    
    # Startup
    await init_db()
    
    # Initialize MQTT service
    mqtt_service = MQTTService(
        broker_host=settings.mqtt_broker_host,
        broker_port=settings.mqtt_broker_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        keepalive=settings.mqtt_keepalive,
    )
    
    # Store in app state for access in routes
    app.state.mqtt_service = mqtt_service
    
    # Connect to MQTT broker (non-blocking, will retry if fails)
    try:
        await mqtt_service.connect()
        await mqtt_service.subscribe_status()
        await mqtt_service.subscribe_lwt()
    except Exception as e:
        print(f"Warning: Could not connect to MQTT broker: {e}")
    
    yield
    
    # Shutdown
    if mqtt_service:
        await mqtt_service.disconnect()


app = FastAPI(
    title="ElBot Backend API",
    description="Backend for ElBot Home Asisten - Smart Home Voice Control",
    version="1.0.0",
    lifespan=lifespan,
)

# Session middleware for authentication
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(devices_router, prefix="/api", dependencies=[Depends(get_current_user)])


@app.get("/")
async def root():
    return {"message": "ElBot Backend API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    mqtt_connected = mqtt_service.is_connected() if mqtt_service else False
    
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_connected,
    }


def get_mqtt_service() -> MQTTService:
    """Dependency for getting MQTT service"""
    return mqtt_service
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_auth.py -v
```

Expected: 6 passed

- [ ] **Step 6: Commit authentication**

```bash
git add backend/app/auth.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add session-based authentication with login/logout"
```

---

## Task 10: MQTT Status Handler Integration

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/mqtt_service.py`

- [ ] **Step 1: Write test for status handler**

```python
# backend/tests/test_status_handler.py
import pytest
import json
from unittest.mock import AsyncMock
from app.core.mqtt_service import MQTTService


@pytest.mark.asyncio
async def test_status_message_updates_database(test_db):
    """Test that MQTT status messages update device state in database"""
    # Create MQTT service
    mqtt_service = MQTTService(
        broker_host="localhost",
        broker_port=1883,
    )
    
    # Setup database callback
    callback = AsyncMock()
    mqtt_service.on_status_message = callback
    
    # Simulate status message
    msg_topic = "elbot/esp32-test/status"
    msg_payload = {
        "device_id": "esp32-test",
        "relay_1": "ON",
        "relay_2": "OFF",
        "relay_3": "OFF",
        "relay_4": "OFF",
        "rssi": -55,
    }
    
    # Process message
    await mqtt_service.on_status_message(msg_topic, msg_payload)
    
    # Verify callback was called
    callback.assert_called_once_with(msg_topic, msg_payload)


@pytest.mark.asyncio
async def test_lwt_message_updates_online_status(test_db):
    """Test that LWT messages update device online status"""
    mqtt_service = MQTTService(
        broker_host="localhost",
        broker_port=1883,
    )
    
    callback = AsyncMock()
    mqtt_service.on_lwt_message = callback
    
    # Simulate offline message
    msg_topic = "elbot/esp32-test/lwt"
    msg_payload = {"status": "offline"}
    
    await mqtt_service.on_lwt_message(msg_topic, msg_payload)
    
    callback.assert_called_once_with(msg_topic, msg_payload)
```

- [ ] **Step 2: Implement status handlers in main.py**

```python
# Add to backend/app/main.py after lifespan function

async def handle_status_message(topic: str, payload: dict):
    """Handle incoming MQTT status messages"""
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import update_device_state
    from datetime import datetime
    
    # Extract device_id from topic
    parts = topic.split("/")
    if len(parts) != 3:
        return
    
    device_id = parts[1]
    
    # Extract relay states from payload
    relay_states = {
        k: v for k, v in payload.items()
        if k.startswith("relay_")
    }
    
    if relay_states:
        async with AsyncSessionLocal() as db:
            device = await update_device_state(db, device_id, relay_states)
            if device:
                device.last_seen = datetime.utcnow()
                await db.commit()


async def handle_lwt_message(topic: str, payload: dict):
    """Handle LWT (online/offline) messages"""
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import get_device
    
    # Extract device_id from topic
    parts = topic.split("/")
    if len(parts) != 3:
        return
    
    device_id = parts[1]
    status = payload.get("status")
    
    async with AsyncSessionLocal() as db:
        device = await get_device(db, device_id)
        if device:
            device.is_online = (status == "online")
            await db.commit()
```

- [ ] **Step 3: Register handlers in lifespan**

```python
# In backend/app/main.py lifespan function, after mqtt_service initialization

    # Setup message handlers
    mqtt_service.on_status_message = handle_status_message
    mqtt_service.on_lwt_message = handle_lwt_message
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_status_handler.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit status handlers**

```bash
git add backend/app/main.py backend/tests/test_status_handler.py
git commit -m "feat: add MQTT status and LWT message handlers with database updates"
```

---

## Task 11: WebSocket Connection Manager

**Files:**
- Create: `backend/app/ws/__init__.py`
- Create: `backend/app/ws/connection_manager.py`
- Test: `backend/tests/test_websocket.py`

- [ ] **Step 1: Write test for WebSocket manager**

```python
# backend/tests/test_websocket.py
import pytest
from app.ws.connection_manager import ConnectionManager


@pytest.fixture
def manager():
    """Create connection manager"""
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect_disconnect(manager):
    """Test connecting and disconnecting clients"""
    from unittest.mock import Mock
    
    websocket = Mock()
    websocket.client.host = "127.0.0.1"
    
    # Connect
    await manager.connect(websocket)
    assert len(manager.active_connections) == 1
    
    # Disconnect
    manager.disconnect(websocket)
    assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_broadcast(manager):
    """Test broadcasting to all clients"""
    from unittest.mock import Mock, AsyncMock
    
    # Create mock websockets
    ws1 = Mock()
    ws1.send_json = AsyncMock()
    
    ws2 = Mock()
    ws2.send_json = AsyncMock()
    
    await manager.connect(ws1)
    await manager.connect(ws2)
    
    # Broadcast message
    await manager.broadcast({"type": "test", "data": "hello"})
    
    # Verify both received
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_send_to_device(manager):
    """Test sending message to specific device's listeners"""
    from unittest.mock import Mock, AsyncMock
    
    ws1 = Mock()
    ws1.send_json = AsyncMock()
    
    ws2 = Mock()
    ws2.send_json = AsyncMock()
    
    await manager.connect(ws1)
    await manager.connect(ws2)
    
    # Subscribe ws1 to device
    manager.subscribe_device("esp32-test", ws1)
    
    # Send to device
    await manager.send_to_device("esp32-test", {"status": "ON"})
    
    # Only ws1 should receive
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_not_called()
```

- [ ] **Step 2: Create ws __init__.py**

```python
# backend/app/ws/__init__.py
# Empty file
```

- [ ] **Step 3: Create connection_manager.py**

```python
# backend/app/ws/connection_manager.py
from typing import List, Dict, Set
from fastapi import WebSocket
from collections import defaultdict


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.device_subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from device subscriptions
        for device_id in list(self.device_subscriptions.keys()):
            if websocket in self.device_subscriptions[device_id]:
                self.device_subscriptions[device_id].remove(websocket)
            
            # Clean up empty subscriptions
            if not self.device_subscriptions[device_id]:
                del self.device_subscriptions[device_id]
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be closed, skip it
                pass
    
    def subscribe_device(self, device_id: str, websocket: WebSocket):
        """Subscribe a client to device updates"""
        self.device_subscriptions[device_id].add(websocket)
    
    def unsubscribe_device(self, device_id: str, websocket: WebSocket):
        """Unsubscribe a client from device updates"""
        if device_id in self.device_subscriptions:
            self.device_subscriptions[device_id].discard(websocket)
    
    async def send_to_device(self, device_id: str, message: dict):
        """Send a message to all clients subscribed to a device"""
        subscribers = self.device_subscriptions.get(device_id, set())
        
        for connection in subscribers:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be closed, skip it
                pass
    
    def get_active_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/test_websocket.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit WebSocket manager**

```bash
git add backend/app/ws/ backend/tests/test_websocket.py
git commit -m "feat: add WebSocket connection manager for real-time updates"
```

---

## Task 12: Final Integration and Documentation

**Files:**
- Create: `backend/README.md`
- Create: `backend/run.sh`

- [ ] **Step 1: Run all tests**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected: All tests pass with good coverage

- [ ] **Step 2: Create README.md**

```markdown
# ElBot Backend Core

Backend API untuk ElBot Home Asisten - Smart Home Voice Control

## Features

- ✅ Device management (CRUD)
- ✅ MQTT integration for device communication
- ✅ REST API with authentication
- ✅ WebSocket support for real-time updates
- ✅ SQLite database with async operations

## Requirements

- Python 3.11+
- Mosquitto MQTT broker (for production)

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Generate password hash:
```bash
python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"
```

5. Update `.env` with the generated hash.

## Running

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the convenience script:
```bash
./run.sh
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

```bash
pytest tests/ -v
```

## Environment Variables

See `.env.example` for all configuration options.

## Next Steps

This is Backend Core (Sub-Project 1/4). Next sub-projects:
- Voice Pipeline + AI Agent
- Web UI
- ESP32 Firmware + OTA
```

- [ ] **Step 3: Create run.sh**

```bash
#!/bin/bash
# Convenience script to run the backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your settings before running."
    exit 1
fi

# Run the application
echo "Starting ElBot Backend..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: Make run.sh executable**

```bash
chmod +x backend/run.sh
```

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "docs: add README and run script for Backend Core"
```

---

## Success Criteria

✅ All tests pass (pytest)  
✅ Can start server without errors  
✅ Can login with password  
✅ Can CRUD devices via REST API  
✅ Can control devices (publishes MQTT commands)  
✅ Can receive MQTT status updates (when broker available)  
✅ Database persists between restarts  
✅ API documentation available at /docs  
✅ Ready for Voice Pipeline integration

---

## Next Sub-Project

After completing Backend Core, proceed to:

**Voice Pipeline + AI Agent** — STT streaming + AI tool calling + TTS streaming

This will add:
- Google STT integration for voice input
- OpenAI-compatible AI Agent with function calling
- Google TTS for voice output
- WebSocket endpoint for real-time voice chat
- Integration with device control tools
