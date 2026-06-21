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
