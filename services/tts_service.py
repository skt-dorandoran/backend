# services/tts_service.py

from __future__ import annotations

import time
import wave
from io import BytesIO
from typing import Tuple
import re

import httpx

class ElevenTTSError(RuntimeError):
    pass

class ElevenTTSService:
    # Voice ID 검증용 정규식 (알파벳, 숫자, 대소문자, 10~64자)
    _VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{10,64}$")

    def __init__(self, api_key: str, model_id: str = "eleven_multilingual_v2"):
        self.api_key = api_key
        self.model_id = model_id

    async def synthesize_pcm_16k(self, voice_id: str, text: str) -> bytes:
        # 1. Voice ID 검증
        voice_id_norm = (voice_id or "").strip()
        
        if not voice_id_norm:
             raise ElevenTTSError("voice_id cannot be empty")
             
        if not self._VOICE_ID_RE.match(voice_id_norm):
             raise ElevenTTSError(f"Invalid voice_id format: {voice_id_norm!r}")

        if not self.api_key:
            raise ElevenTTSError("ELEVENLABS_API_KEY is empty")

        # [핵심 수정] params 딕셔너리 사용 중단 -> URL에 직접 포함
        # urllib 테스트가 성공한 방식과 동일하게 만듭니다.
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id_norm}?output_format=pcm_16000"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "text": text,
            "model_id": self.model_id,
        }

        # [핵심 수정] trust_env=False 유지 (프록시 설정 무시)
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            # params=params 인자 제거!
            r = await client.post(url, headers=headers, json=payload)

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            
            # 디버깅용 로그 강화
            raise ElevenTTSError(
                f"ElevenLabs TTS failed: {r.status_code} {detail} | "
                f"Target URL: {url}"
            )

        return r.content

    # ... (pcm_to_wav, wav_duration_ms, synthesize_wav_with_metrics 메서드는 기존과 동일)
    @staticmethod
    def pcm_to_wav(pcm_s16le: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
        buf = BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_s16le)
        return buf.getvalue()

    @staticmethod
    def wav_duration_ms(wav_bytes: bytes) -> Tuple[int, int]:
        buf = BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            frames = wf.getnframes()
            sr = wf.getframerate()
        duration_ms = int(frames * 1000 / sr) if sr else 0
        return duration_ms, sr

    async def synthesize_wav_with_metrics(self, voice_id: str, text: str) -> Tuple[bytes, dict]:
        t0 = time.perf_counter()
        t_model0 = time.perf_counter()
        
        # 호출
        pcm = await self.synthesize_pcm_16k(voice_id=voice_id, text=text)
        
        t_tts_done = time.perf_counter()

        wav_bytes = self.pcm_to_wav(pcm)
        duration_ms, sr = self.wav_duration_ms(wav_bytes)

        metrics = {
            "duration_ms": duration_ms,
            "sample_rate": sr,
            "processing_ms": int((time.perf_counter() - t0) * 1000),
            "model_load_ms": int((t_tts_done - t_model0) * 1000),
            "tts_ms": int((t_tts_done - t_model0) * 1000),
        }
        return wav_bytes, metrics
