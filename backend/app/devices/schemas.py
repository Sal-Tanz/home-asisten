from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
from datetime import datetime
import json


class DeviceCreate(BaseModel):
    """Schema for creating a new device"""
    device_id: str = Field(..., description="Unique device identifier (e.g., ESP32 MAC)")
    name: str = Field(..., description="Human-readable device name")
    room: str = Field(..., description="Room location")
    type: str = Field(default="relay", description="Device type")
    relay_count: int = Field(default=4, ge=1, le=8, description="Number of relays")
    relay_names: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom names for each relay")


class DeviceUpdate(BaseModel):
    """Schema for updating device fields (all optional)"""
    name: Optional[str] = None
    room: Optional[str] = None
    type: Optional[str] = None
    relay_count: Optional[int] = Field(None, ge=1, le=8)
    relay_names: Optional[Dict[str, str]] = Field(None, description="Custom names for each relay")
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
    relay_names: Dict[str, str]
    state: Dict[str, str]  # Dict for API response (stored as JSON string in DB)
    is_online: bool
    last_seen: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    @field_validator('state', mode='before')
    @classmethod
    def parse_state(cls, v):
        """Parse state from JSON string to dict if needed"""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator('relay_names', mode='before')
    @classmethod
    def parse_relay_names(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v or {}

    class Config:
        from_attributes = True
