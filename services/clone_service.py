from __future__ import annotations

from io import BytesIO
from typing import List, Dict, Any

from elevenlabs.client import ElevenLabs


class ElevenLabsService:
    def __init__(self, api_key: str):
        self.client = ElevenLabs(api_key=api_key)

    def create_voice_clone(self, name: str, file_bytes_list: List[bytes]) -> str:
        files = [BytesIO(b) for b in file_bytes_list]
        try:
            voice = self.client.voices.ivc.create(
                name=name,
                files=files,
            )
        except Exception as e:
            raise RuntimeError(f"ElevenLabs ivc.create failed: {e}") from e

        return voice.voice_id

    def auth_check(self) -> Dict[str, Any]:
        """
        ElevenLabs API Key 인증이 유효한지 간단히 확인:
        - voices 목록을 조회해보고 성공/실패를 반환
        """
        try:
            voices = self.client.voices.get_all()
            # SDK 반환 타입이 리스트/객체 모두 가능하므로 안전하게 처리
            count = None
            if isinstance(voices, list):
                count = len(voices)
            else:
                # 일부 SDK는 voices.voices 형태로 감싸서 반환
                inner = getattr(voices, "voices", None)
                if isinstance(inner, list):
                    count = len(inner)

            return {
                "ok": True,
                "voicesCount": count,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }
