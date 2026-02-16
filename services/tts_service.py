from __future__ import annotations

import time
import wave
from io import BytesIO
from typing import Tuple, Optional

import httpx


class ElevenTTSError(RuntimeError):
    pass


class ElevenTTSService:
    def __init__(self, api_key: str, model_id: str = "eleven_multilingual_v2"):
        self.api_key = api_key
        self.model_id = model_id

    async def synthesize_pcm_16k(self, voice_id: str, text: str) -> bytes:
        """
        ElevenLabs TTS convert로 PCM(S16LE) 16kHz raw bytes를 받아온다.
        """
        if not voice_id or not voice_id.strip():
            raise ValueError("voice_id cannot be empty")
    
        if not self.api_key:
            raise ElevenTTSError("ELEVENLABS_API_KEY is empty")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        params = {"output_format": "pcm_16000"}  # enum에 포함 :contentReference[oaicite:4]{index=4}
        headers = {
            "xi-api-key": self.api_key,          # 인증 헤더 :contentReference[oaicite:5]{index=5}
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,           # 문서에 존재 :contentReference[oaicite:6]{index=6}
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, params=params, headers=headers, json=payload)

        if r.status_code != 200:
            # ElevenLabs는 JSON 에러를 주는 경우가 많아서 그대로 노출
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise ElevenTTSError(f"ElevenLabs TTS failed: {r.status_code} {detail}")

        return r.content  # raw PCM bytes

    @staticmethod
    def pcm_to_wav(pcm_s16le: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
        """
        raw PCM(S16LE) -> WAV 컨테이너로 래핑
        """
        buf = BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_s16le)
        return buf.getvalue()

    @staticmethod
    def wav_duration_ms(wav_bytes: bytes) -> Tuple[int, int]:
        """
        WAV 바이트에서 duration(ms), sample_rate를 계산
        """
        buf = BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            frames = wf.getnframes()
            sr = wf.getframerate()
        duration_ms = int(frames * 1000 / sr) if sr else 0
        return duration_ms, sr

    async def synthesize_wav_with_metrics(self, voice_id: str, text: str) -> Tuple[bytes, dict]:
        """
        WAV bytes + 메트릭(헤더용) 반환
        """
        t0 = time.perf_counter()

        # "모델 로드 시간"은 ElevenLabs 쪽 모델 로딩 개념이 외부에 드러나지 않으므로
        # 여기서는 '요청 준비/첫 호출 오버헤드'를 모델 로드로 잡아 근사치로 반환(일관성 목적)
        t_model0 = time.perf_counter()
        pcm = await self.synthesize_pcm_16k(voice_id=voice_id, text=text)
        t_tts_done = time.perf_counter()

        wav_bytes = self.pcm_to_wav(pcm, sample_rate=16000, channels=1)
        duration_ms, sr = self.wav_duration_ms(wav_bytes)

        metrics = {
            "duration_ms": duration_ms,
            "sample_rate": sr,
            "processing_ms": int((time.perf_counter() - t0) * 1000),
            "model_load_ms": int((t_tts_done - t_model0) * 1000),  # 근사
            "tts_ms": int((t_tts_done - t_model0) * 1000),
        }
        return wav_bytes, metrics
