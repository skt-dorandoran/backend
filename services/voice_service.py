import uuid
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import HTTPException, UploadFile

from core.settings import settings
from schemas.voice_schema import UploadVoiceSampleResponse


def _utc_now_iso_z() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()


class VoiceService:
    def __init__(self) -> None:
        base_url = settings.ELEVENLABS_BASE_URL.strip()
        
        # 빈 문자열이면 기본값 사용
        if not base_url:
            base_url = "https://api.elevenlabs.io"
            # print("⚠️  ELEVENLABS_BASE_URL이 비어있어 기본값 사용")
        
        # 프로토콜 확인
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"https://{base_url}"
            # print(f"⚠️  프로토콜이 없어서 추가: {base_url}")
        
        self.base_url = base_url.rstrip("/")
        self.api_key = settings.ELEVENLABS_API_KEY
        
        # 초기화 확인 (디버깅용, 나중에 제거 가능)
        # print(f"✅ VoiceService 초기화:")
        # print(f"   - Base URL: {self.base_url}")
        # print(f"   - API Key exists: {bool(self.api_key)}")
        
    _in_memory_meta: Dict[str, Dict[str, Any]] = {}

    # m4a 추가
    allowed_formats = {"wav", "mp3", "m4a"}

    # content-type -> format 매핑
    content_type_map = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/aac": "m4a",  # 환경에 따라 m4a를 이렇게 보내는 경우도 있음
    }

    def _normalize_format(self, s: Optional[str]) -> str:
        # Swagger 기본 placeholder "string" 같은 값 방어 + 따옴표 제거
        if not s:
            return ""
        s = s.strip().lower()
        # 양쪽 따옴표 제거
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip().lower()
        # swagger placeholder 방어
        if s == "string":
            return ""
        return s

    def _infer_format(self, audio_file: UploadFile) -> str:
        # 1) filename 확장자 우선
        filename = (audio_file.filename or "").lower()
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in self.allowed_formats:
            return ext

        # 2) content_type 기반 추론
        ct = (audio_file.content_type or "").lower().strip()
        inferred = self.content_type_map.get(ct, "")
        if inferred in self.allowed_formats:
            return inferred

        return ""

    async def upload_sample(
        self,
        sample_name: str,
        audio_file: UploadFile,
        audio_format: str,
        duration: int,
        sample_rate: int,
    ) -> UploadVoiceSampleResponse:
        # 1) 일단 클라이언트 값 정규화
        fmt = self._normalize_format(audio_format)

        # 2) 유효하지 않거나 비어 있으면 파일로부터 추론
        if fmt not in self.allowed_formats:
            fmt = self._infer_format(audio_file)

        # 3) 그래도 모르면 400
        if fmt not in self.allowed_formats:
            raise ValueError('audioFormat must be one of: "wav", "mp3", "m4a" (or inferable from file)')

        upload_id = f"upload_{datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        sample_id = f"sample_{uuid.uuid4().hex}"

        safe_name = "".join(c for c in sample_name if c.isalnum() or c in ("-", "_")).strip() or "sample"
        save_dir = settings.UPLOAD_DIR / upload_id
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{safe_name}.{fmt}"

        # 파일 저장
        with save_path.open("wb") as f:
            while True:
                chunk = await audio_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        uploaded_at = _utc_now_iso_z()
        timestamp = _utc_now_iso_z()

        self._in_memory_meta[sample_id] = {
            "uploadId": upload_id,
            "sampleId": sample_id,
            "sampleName": sample_name,
            "duration": duration,
            "sampleRate": sample_rate,
            "audioFormat": fmt,
            "uploadedAt": uploaded_at,
            "filePath": str(save_path),
            "originalFilename": audio_file.filename,
            "contentType": audio_file.content_type,
        }

        return UploadVoiceSampleResponse(
            uploadId=upload_id,
            sampleId=sample_id,
            sampleName=sample_name,
            duration=duration,
            uploadedAt=uploaded_at,
            nextStep="train_voice_clone",
            message="음성 샘플이 성공적으로 업로드되었습니다",
            timestamp=timestamp,
        )
    
    async def delete_voice(self, voice_id: str) -> dict:
        url = f"{self.base_url}/v1/voices/{voice_id}"

        headers = {
            "xi-api-key": self.api_key,
            "accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.delete(url, headers=headers)

        # 200이면 보통 {"status":"ok"} 형태 :contentReference[oaicite:3]{index=3}
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:
                # 혹시 JSON 파싱 실패해도 내부 응답 규격을 맞춰줌
                return {"status": "ok"}

        # ElevenLabs 에러 바디를 그대로 전달(가능한 경우)
        detail = None
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text

        # 내부 표준화: upstream 에러를 502로 래핑
        raise HTTPException(
            status_code=502,
            detail={
                "message": "ElevenLabs delete_voice failed",
                "status_code": resp.status_code,
                "upstream": detail,
            },
        )
