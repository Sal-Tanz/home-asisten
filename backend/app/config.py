from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_password_hash: str
    secret_key: str
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./elbot.db"
    mqtt_broker_host: str = "test.mosquitto.org"
    mqtt_broker_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_keepalive: int = 60

    # AI API
    ai_api_base_url: str = "https://api-ai.elektrounsub.com/v1"
    ai_api_key: str = ""
    ai_model_name: str = "nvidia/openai/gpt-oss-120b"

    # STT
    google_stt_key: str = ""
    google_stt_url: str = "https://www.google.com/speech-api/v2/recognize"

    # TTS
    tts_voice: str = "id-ID-ArdiNeural"
    tts_rate: str = "+0%"
    tts_volume: str = "+0%"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
