from __future__ import annotations

import time
import wave
from io import BytesIO
from typing import Tuple
import re
from urllib.parse import quote

import httpx


class ElevenTTSError(RuntimeError):
    pass


class ElevenTTSService:
    # voice_id에 슬래시/공백/특수문자 섞이는 케이스를 서버에서 조기에 차단
    _VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{10,64}$")

    def __init__(self, api_key: str, model_id: str = "eleven_multilingual_v2"):
        self.api_key = api_key
        self.model_id = model_id

    async def synthesize_pcm_16k(self, voice_id: str, text: str) -> bytes:
        """
        ElevenLabs TTS convert로 PCM(S16LE) 16kHz raw bytes를 받아온다.
        """
        # (1) 정규화: URL에 넣기 전에 반드시 strip된 값 사용
        voice_id_norm = (voice_id or "").strip()
        if not voice_id_norm:
            raise ElevenTTSError("voice_id cannot be empty")

        # (2) 패턴 검증: path 깨는 문자(/, ?, #, 공백 등) 차단
        if not self._VOICE_ID_RE.match(voice_id_norm):
            raise ElevenTTSError(f"voice_id looks invalid: repr={voice_id_norm!r}")

        if not self.api_key:
            raise ElevenTTSError("ELEVENLABS_API_KEY is empty")

        # (3) 안전 인코딩: 혹시 모를 특수문자 방지 (safe=''로 완전 인코딩)
        voice_id_path = quote(voice_id_norm, safe="")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id_path}"

        params = {"output_format": "pcm_16000"}
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, params=params, headers=headers, json=payload)

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text

            # (4) 서버 원인 강제 노출: 실제 요청 URL + voice_id repr 포함
            req_url = ""
            try:
                req_url = str(r.request.url)
            except Exception:
                req_url = "<no request url>"

            raise ElevenTTSError(
                f"ElevenLabs TTS failed: {r.status_code} {detail} | "
                f"voice_id_repr={voice_id_norm!r} | request_url={req_url}"
            )

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

        t_model0 = time.perf_counter()
        pcm = await self.synthesize_pcm_16k(voice_id=voice_id, text=text)
        t_tts_done = time.perf_counter()

        wav_bytes = self.pcm_to_wav(pcm, sample_rate=16000, channels=1)
        duration_ms, sr = self.wav_duration_ms(wav_bytes)

        metrics = {
            "duration_ms": duration_ms,
            "sample_rate": sr,
            "processing_ms": int((time.perf_counter() - t0) * 1000),
            "model_load_ms": int((t_tts_done - t_model0) * 1000),
            "tts_ms": int((t_tts_done - t_model0) * 1000),
        }
        return wav_bytes, metrics
