from __future__ import annotations

import time
import wave
import json
import urllib.request
import urllib.error
import asyncio
from io import BytesIO
from typing import Tuple
import re

# httpx 제거 (더 이상 사용하지 않음)
# import httpx 

class ElevenTTSError(RuntimeError):
    pass

class ElevenTTSService:
    _VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{10,64}$")

    def __init__(self, api_key: str, model_id: str = "eleven_multilingual_v2"):
        self.api_key = api_key
        self.model_id = model_id

    # 동기 함수: 실제 통신을 수행 (아까 성공한 테스트 코드 기반)
    def _synthesize_sync(self, url: str, headers: dict, payload: dict) -> bytes:
        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=json_data, method="POST")
        
        for k, v in headers.items():
            req.add_header(k, v)
            
        try:
            # SSL 컨텍스트 등은 기본값 사용 (테스트 성공 환경과 동일하게)
            with urllib.request.urlopen(req) as response:
                if response.getcode() != 200:
                    raise ElevenTTSError(f"Status {response.getcode()}")
                return response.read()
        except urllib.error.HTTPError as e:
            # 에러 응답 본문 읽기
            err_body = e.read().decode('utf-8')
            raise ElevenTTSError(f"ElevenLabs TTS failed: {e.code} {err_body} | URL: {url}")
        except Exception as e:
            raise ElevenTTSError(f"Connection failed: {str(e)} | URL: {url}")

    async def synthesize_pcm_16k(self, voice_id: str, text: str) -> bytes:
        """
        ElevenLabs TTS (urllib 기반, 비동기 래핑)
        """
        # 1. 검증
        voice_id_norm = (voice_id or "").strip()
        if not voice_id_norm:
             raise ElevenTTSError("voice_id cannot be empty")
        if not self._VOICE_ID_RE.match(voice_id_norm):
             raise ElevenTTSError(f"Invalid voice_id format: {voice_id_norm!r}")
        if not self.api_key:
            raise ElevenTTSError("ELEVENLABS_API_KEY is empty")

        # 2. URL 구성 (쿼리 스트링 포함)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id_norm}?output_format=pcm_16000"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Python-urllib/3.9", # 봇 차단 방지용 기본 헤더
        }
        
        payload = {
            "text": text,
            "model_id": self.model_id,
        }

        # 3. 비동기 실행 (스레드 풀에서 urllib 실행)
        # run_in_executor를 사용하여 메인 스레드를 차단하지 않고 동기 함수 실행
        loop = asyncio.get_running_loop()
        
        try:
            # _synthesize_sync 함수를 별도 스레드에서 실행하고 결과를 기다림
            result = await loop.run_in_executor(None, self._synthesize_sync, url, headers, payload)
            return result
        except ElevenTTSError as e:
            # 이미 처리된 에러는 그대로 전파
            raise e
        except Exception as e:
            # 그 외 에러 처리
            raise ElevenTTSError(f"Unexpected error in TTS service: {e}")

    # ... (pcm_to_wav, wav_duration_ms, synthesize_wav_with_metrics는 기존과 동일하게 유지)
    
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
