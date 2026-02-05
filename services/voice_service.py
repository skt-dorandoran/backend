import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import UploadFile

from core.settings import settings
from schemas.voice_schema import UploadVoiceSampleResponse


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class VoiceService:
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

        upload_id = f"upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
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
