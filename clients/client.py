import json
import time
import asyncio
from typing import AsyncIterator, Optional, Dict, Any

import websockets


class DeepgramStreamingClient:
    """
    Deepgram Live WS 클라이언트 (오디오 입력 → transcript 이벤트 출력)
    """
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "nova-3",
        language: str = "ko",
        encoding: Optional[str] = None,        # raw PCM이면 "linear16"
        sample_rate: Optional[int] = None,     # raw PCM이면 16000
        channels: int = 1,
        interim_results: bool = True,
        endpointing_ms: int = 300,
        vad_events: bool = True,
        punctuate: bool = True,
        smart_format: bool = True,
    ):
        self.api_key = api_key
        self.model = model
        self.language = language
        self.encoding = encoding
        self.sample_rate = sample_rate
        self.channels = channels
        self.interim_results = interim_results
        self.endpointing_ms = endpointing_ms
        self.vad_events = vad_events
        self.punctuate = punctuate
        self.smart_format = smart_format

        self._ws = None

    def _build_url(self) -> str:
        # Deepgram v1 listen streaming
        # raw PCM이면 encoding/sample_rate 필수
        params = {
            "model": self.model,
            "language": self.language,
            "interim_results": "true" if self.interim_results else "false",
            "endpointing": str(self.endpointing_ms),
            "vad_events": "true" if self.vad_events else "false",
            "punctuate": "true" if self.punctuate else "false",
            "smart_format": "true" if self.smart_format else "false",
            "channels": str(self.channels),
        }
        if self.encoding:
            params["encoding"] = self.encoding
        if self.sample_rate:
            params["sample_rate"] = str(self.sample_rate)

        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"wss://api.deepgram.com/v1/listen?{qs}"

    async def __aenter__(self):
        if not self.api_key or not self.api_key.strip():
            raise RuntimeError("DEEPGRAM_API_KEY is empty (not loaded from env/.env)")
        
        url = self._build_url()
        headers = {"Authorization": f"Token {self.api_key}"}
        self._ws = await websockets.connect(url, additional_headers=headers, ping_interval=None)

        print("[Deepgram] URL:", url)
        print("[Deepgram] Has key:", bool(self.api_key and self.api_key.strip()))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._ws:
                await self._ws.close()
        finally:
            self._ws = None

    async def send_audio(self, chunk: bytes) -> None:
        # 빈 바이트 전송은 문제를 만들 수 있어 방어
        if not chunk:
            return
        await self._ws.send(chunk)

    async def send_keepalive(self) -> None:
        # Deepgram KeepAlive 메시지
        await self._ws.send(json.dumps({"type": "KeepAlive"}))

    async def send_finalize(self) -> None:
        # Deepgram Finalize 메시지 (남아있는 버퍼 강제 마감)
        await self._ws.send(json.dumps({"type": "Finalize"}))

    async def recv_events(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Deepgram에서 오는 메시지(JSON 문자열)를 dict로 파싱하여 yield
        """
        async for msg in self._ws:
            # msg는 보통 str(JSON). 때로 bytes일 수도 있어 처리
            if isinstance(msg, (bytes, bytearray)):
                try:
                    msg = msg.decode("utf-8", errors="ignore")
                except Exception:
                    continue
            try:
                data = json.loads(msg)
            except Exception:
                continue
            yield data
