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

router = APIRouter(tags=["devices"])


@router.post("/devices", response_model=DeviceResponse)
async def create_device_endpoint(
    device_data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new device"""
    existing = await get_device(db, device_data.device_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Device with device_id '{device_data.device_id}' already exists",
        )

    device = await create_device(db, device_data)

    return DeviceResponse.model_validate(device)


@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get all devices"""
    devices = await get_devices(db, skip=skip, limit=limit)

    return [DeviceResponse.model_validate(device) for device in devices]


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device_endpoint(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific device"""
    device = await get_device(db, device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse.model_validate(device)


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

    return DeviceResponse.model_validate(device)


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
