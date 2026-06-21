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
