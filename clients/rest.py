import time
import httpx
from typing import Any, Dict, Optional

from core.settings import settings


DEEPGRAM_REST_URL = "https://api.deepgram.com/v1/listen"


async def transcribe_prerecorded(
    file_bytes: bytes,
    *,
    content_type: str,
    model: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deepgram prerecorded(REST) STT
    - 입력: 일반 미디어 파일 바이트(wav/mp3/webm 등)
    - 출력: Deepgram JSON 응답(dict)
    """
    if not settings.DEEPGRAM_API_KEY or not settings.DEEPGRAM_API_KEY.strip():
        raise RuntimeError("DEEPGRAM_API_KEY is empty")

    params = {
        "model": model or settings.DEEPGRAM_MODEL,
        "language": language or settings.DEEPGRAM_LANGUAGE,
        "punctuate": "true",
        "smart_format": "true",
    }

    headers = {
        "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
        "Content-Type": content_type,  # 중요: audio/wav, audio/mpeg, audio/webm ...
    }

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            DEEPGRAM_REST_URL,
            params=params,
            headers=headers,
            content=file_bytes,
        )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 오류면 본문까지 같이 던져서 디버깅 쉽게
    if resp.status_code >= 400:
        raise RuntimeError(f"Deepgram REST error {resp.status_code}: {resp.text}")

    data = resp.json()
    data["_processing_ms"] = elapsed_ms
    return data
