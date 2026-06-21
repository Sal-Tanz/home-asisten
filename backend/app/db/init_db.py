from app.db.database import engine, Base
# Import models so they are registered with Base.metadata
from app.devices.models import Device, ActionLog


async def init_db():
    """Create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
