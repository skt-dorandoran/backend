import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

def is_local() -> bool:
    return os.getenv("ENV", "local").lower() == "local"

class Settings(BaseSettings):
    ENV: str = "local"

    # STT (Deepgram) 설정
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_MODEL: str = "nova-3"
    DEEPGRAM_LANGUAGE: str = "ko"
    DEEPGRAM_ENDPOINTING_MS: int = 300

    # 음성 파일 업로드 디렉토리
    UPLOAD_DIR: Path = Path("uploads/voice_samples")

    # 로컬일 때만 .env를 보도록 설정
    model_config = SettingsConfigDict(
        env_file=".env" if is_local() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
