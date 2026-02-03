import os
from pydantic_settings import BaseSettings, SettingsConfigDict

def is_local() -> bool:
    return os.getenv("ENV", "local").lower() == "local"

class Settings(BaseSettings):
    ENV: str = "local"
    OPENAI_API_KEY: str

    # 로컬일 때만 .env를 보도록 설정
    model_config = SettingsConfigDict(
        env_file=".env" if is_local() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
