import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

def is_local() -> bool:
    """로컬 환경인지 확인"""
    # 1. CI 환경이면 무조건 로컬 아님
    if os.getenv("CI"):
        return False
    # 2. ENV 변수 확인 (없으면 로컬로 간주)
    env = os.getenv("ENV", "").lower()
    return env in ("", "local")

# 로컬일 때만 .env 로드
if is_local():
    from dotenv import load_dotenv
    # print("🔧 로컬 환경 감지: .env 파일을 로드합니다.")
    load_dotenv(dotenv_path=".env", override=True)
else:
    # print("☁️  프로덕션 환경 감지: 환경변수를 사용합니다.")
    pass

class Settings(BaseSettings):
    # ENV의 기본값을 동적으로 설정
    ENV: str = os.getenv("ENV", "local")  # 이 부분 수정
    
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

    model_config = SettingsConfigDict(
        env_file=".env" if is_local() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

# 디버깅용 출력
# print(f"📍 현재 환경: {settings.ENV}")
# print(f"🔑 DEEPGRAM_API_KEY 설정됨: {bool(settings.DEEPGRAM_API_KEY)}")
# print(f"🔑 OPENAI_API_KEY 설정됨: {bool(settings.OPENAI_API_KEY)}")
# print(f"🔑 ELEVENLABS_API_KEY 설정됨: {bool(settings.ELEVENLABS_API_KEY)}")

# 디렉토리 생성
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PERSONA_DIR.mkdir(parents=True, exist_ok=True)
settings.ONBOARDING_DIR.mkdir(parents=True, exist_ok=True)