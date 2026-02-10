import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

def is_local() -> bool:
    return os.getenv("ENV", "local").lower() == "local"

if is_local():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env", override=True)

class Settings(BaseSettings):
    ENV: str = "local"

    # Deepgram 설정
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_MODEL: str = "nova-3"
    DEEPGRAM_LANGUAGE: str = "ko"
    DEEPGRAM_ENDPOINTING_MS: int = 300

    # OpenAI 설정
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # ElevenLabs 설정
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_TTS_MODEL_ID: str = "eleven_multilingual_v2"
    ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io"

    # 파일 업로드 디렉토리
    UPLOAD_DIR: Path = Path("uploads/voice_samples")
    PERSONA_DIR: Path = Path("uploads/personas")
    ONBOARDING_DIR: Path = Path("uploads/onboarding")

    # 로컬일 때만 .env를 보도록 설정
    model_config = SettingsConfigDict(
        env_file=".env" if is_local() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PERSONA_DIR.mkdir(parents=True, exist_ok=True)
settings.ONBOARDING_DIR.mkdir(parents=True, exist_ok=True)