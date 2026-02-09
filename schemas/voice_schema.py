from pydantic import BaseModel, Field
from typing import Literal, Optional


class UploadVoiceSampleResponse(BaseModel):
    uploadId: str
    sampleId: str
    sampleName: str
    duration: int = Field(ge=0, description="샘플 길이 (밀리초)")
    uploadedAt: str  # ISO 8601 (UTC, Z)
    nextStep: Literal["train_voice_clone"]
    message: str
    timestamp: str  # ISO 8601 (UTC, Z)


class VoiceDeleteRequest(BaseModel):
    voiceId: Optional[str] = Field(default=None, description="삭제할 음성 모델 ID")


class VoiceDeleteResponse(BaseModel):
    status: str = Field(description="삭제 결과 상태(성공 시 ok)")
