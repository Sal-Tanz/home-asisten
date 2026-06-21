# backend/app/main.py
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
from app.config import get_settings
from app.db.init_db import init_db
from app.core.mqtt_service import MQTTService
from app.devices.router import router as devices_router
from app.auth import router as auth_router, get_current_user
import socketio
from app.chat.router import sio, sessions as chat_sessions

settings = get_settings()


async def handle_status_message(topic: str, payload: dict):
    """Handle incoming MQTT status messages and update device state in database"""
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import update_device_state
    from datetime import datetime

    # Extract device_id from topic: elbot/<device_id>/status
    parts = topic.split("/")
    if len(parts) != 3:
        return

    device_id = parts[1]

    # Extract relay states from payload (keys starting with "relay_")
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
    """Handle LWT (online/offline) messages and update device online status"""
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import get_device

    # Extract device_id from topic: elbot/<device_id>/lwt
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


# Global MQTT service instance
mqtt_service: Optional[MQTTService] = None


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

    # Setup message handlers
    mqtt_service.on_status_message = handle_status_message
    mqtt_service.on_lwt_message = handle_lwt_message

    # Connect to MQTT broker (non-blocking, will retry if fails)
    try:
        await mqtt_service.connect()
        await mqtt_service.subscribe_status()
        await mqtt_service.subscribe_lwt()
    except Exception as e:
        print(f"Warning: Could not connect to MQTT broker: {e}")

    # Start background task for stale session cleanup
    cleanup_task = asyncio.create_task(_cleanup_stale_sessions())

    yield

    # Shutdown
    if mqtt_service:
        await mqtt_service.disconnect()

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


async def _cleanup_stale_sessions():
    """Periodically clean up inactive chat sessions (every 5 minutes)."""
    while True:
        await asyncio.sleep(300)
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        stale = [sid for sid, s in chat_sessions.items() if s.last_activity < cutoff]
        for sid in stale:
            chat_sessions.pop(sid, None)


app = FastAPI(
    title="ElBot Backend API",
    description="Backend for ElBot Home Asisten - Smart Home Voice Control",
    version="1.0.0",
    lifespan=lifespan,
)

# Session middleware
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
app.include_router(
    devices_router,
    prefix="/api",
    dependencies=[Depends(get_current_user)],
)


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.get("/login")
async def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/settings")
async def settings_page(request: Request):
    return FileResponse(FRONTEND_DIR / "settings.html")


@app.get("/")
async def index_page(request: Request):
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/hello")
async def api_hello():
    return {"message": "ElBot Backend API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    mqtt_connected = mqtt_service.is_connected() if mqtt_service else False

    return {
        "status": "healthy",
        "mqtt_connected": mqtt_connected,
    }


# Serve static files
static_dir = FRONTEND_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def get_mqtt_service() -> MQTTService:
    """Dependency for getting MQTT service"""
    return mqtt_service


# Wrap FastAPI with Socket.IO ASGI app
# Socket.IO handles /socket.io/* paths, FastAPI handles everything else
app = socketio.ASGIApp(sio, other_asgi_app=app)
