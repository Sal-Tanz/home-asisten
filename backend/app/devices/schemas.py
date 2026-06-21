from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class DeviceCreate(BaseModel):
    """Schema for creating a new device"""
    device_id: str = Field(..., description="Unique device identifier (e.g., ESP32 MAC)")
    name: str = Field(..., description="Human-readable device name")
    room: str = Field(..., description="Room location")
    type: str = Field(default="relay", description="Device type")
    relay_count: int = Field(default=4, ge=1, le=8, description="Number of relays")


class DeviceUpdate(BaseModel):
    """Schema for updating device fields (all optional)"""
    name: Optional[str] = None
    room: Optional[str] = None
    type: Optional[str] = None
    relay_count: Optional[int] = Field(None, ge=1, le=8)
    is_online: Optional[bool] = None


class DeviceControlRequest(BaseModel):
    """Schema for controlling device relays"""
    relay: str = Field(..., description="Relay identifier (e.g., 'relay_1')")
    action: str = Field(..., description="Action to perform: 'ON' or 'OFF'")


class DeviceResponse(BaseModel):
    """Schema for device response"""
    id: int
    device_id: str
    name: str
    room: str
    type: str
    relay_count: int
    state: str  # JSON string
    is_online: bool
    last_seen: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
