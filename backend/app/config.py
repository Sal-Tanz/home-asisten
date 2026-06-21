from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_password_hash: str
    secret_key: str
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./elbot.db"
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
