from pydantic import BaseModel, Field
from typing import Literal


class UploadVoiceSampleResponse(BaseModel):
    uploadId: str
    sampleId: str
    sampleName: str
    duration: int = Field(ge=0, description="샘플 길이 (밀리초)")
    uploadedAt: str  # ISO 8601 (UTC, Z)
    nextStep: Literal["train_voice_clone"]
    message: str
    timestamp: str  # ISO 8601 (UTC, Z)
