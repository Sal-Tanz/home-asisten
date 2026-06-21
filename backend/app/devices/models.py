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
