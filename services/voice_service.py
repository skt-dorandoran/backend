import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from fastapi import UploadFile

from core.settings import settings
from schemas.voice_schema import UploadVoiceSampleResponse


def _utc_now_iso_z() -> str:
    # 예: 2024-02-04T10:15:00Z
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class SavedSample:
    upload_id: str
    sample_id: str
    file_path: Path
    meta: Dict[str, Any]


class VoiceService:
    """
    - DB 없음: 파일은 디스크에 저장, 메타데이터는 프로세스 메모리에 유지(예시)
    - 운영 환경이면 메타도 파일/Redis/DB 등으로 영속화 필요
    """
    _in_memory_meta: Dict[str, Dict[str, Any]] = {}

    allowed_formats = {"wav", "mp3"}

    async def upload_sample(
        self,
        sample_name: str,
        audio_file: UploadFile,
        audio_format: str,
        duration: int,
        sample_rate: int,
    ) -> UploadVoiceSampleResponse:
        fmt = (audio_format or "").lower().strip()
        if fmt not in self.allowed_formats:
            raise ValueError('audioFormat must be one of: "wav", "mp3"')

        # 간단한 확장자/콘텐츠 검사(명세 밖의 추가 필드/변형은 없음)
        filename = audio_file.filename or f"sample.{fmt}"
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext and ext != fmt:
            # 파일명이 mp3인데 audioFormat이 wav 같은 케이스 방지
            raise ValueError("audioFormat does not match audioFile extension")

        upload_id = f"upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        sample_id = f"sample_{uuid.uuid4().hex}"

        # 저장 경로
        safe_name = "".join(c for c in sample_name if c.isalnum() or c in ("-", "_")).strip() or "sample"
        save_dir = settings.UPLOAD_DIR / upload_id
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{safe_name}.{fmt}"

        # 파일 저장 (multipart/form-data 바이너리 그대로)
        with save_path.open("wb") as f:
            while True:
                chunk = await audio_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        uploaded_at = _utc_now_iso_z()
        timestamp = _utc_now_iso_z()

        meta = {
            "uploadId": upload_id,
            "sampleId": sample_id,
            "sampleName": sample_name,
            "duration": duration,
            "sampleRate": sample_rate,
            "audioFormat": fmt,
            "uploadedAt": uploaded_at,
            "filePath": str(save_path),
        }
        self._in_memory_meta[sample_id] = meta

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
