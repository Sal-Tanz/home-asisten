import json
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.devices.models import Device, ActionLog
from app.devices.schemas import DeviceCreate, DeviceUpdate


async def create_device(db: AsyncSession, device_data: DeviceCreate) -> Device:
    """Create a new device with all relays initialized to OFF"""
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
    """Get a device by its device_id"""
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    return result.scalar_one_or_none()


async def get_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Device]:
    """Get all devices with pagination"""
    result = await db.execute(select(Device).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_device(
    db: AsyncSession, device_id: str, device_data: DeviceUpdate
) -> Optional[Device]:
    """Update a device's fields (only provided fields)"""
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
    """Delete a device by device_id"""
    device = await get_device(db, device_id)
    if not device:
        return False
    
    await db.delete(device)
    await db.commit()
    return True


async def update_device_state(
    db: AsyncSession, device_id: str, new_state: dict
) -> Optional[Device]:
    """Update device relay state (called when MQTT status received)"""
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
    """Get action logs for a device, newest first"""
    result = await db.execute(
        select(ActionLog)
        .where(ActionLog.device_id == device_id)
        .order_by(ActionLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())
