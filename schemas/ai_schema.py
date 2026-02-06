from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class ConversationMessage(BaseModel):
    role: Literal["other", "user"]
    text: str


class GenerateResponseRequest(BaseModel):
    callId: str
    userSpeech: str = Field(..., description="상대방의 발화")
    conversationHistory: List[ConversationMessage] = Field(default_factory=list)
    phoneNumber: Optional[str] = None


class ResponseItem(BaseModel):
    id: str
    text: str
    tone: Literal["friendly", "formal", "casual", "professional"]
    priority: int = Field(ge=1, le=3)


class GenerateResponseResponse(BaseModel):
    callId: str
    responses: List[ResponseItem]
    generatedAt: str  # ISO 8601 (UTC, Z)
    processingTime: float = Field(description="처리 시간 (초)")


# ── 음성 교정 (correct-pronunciation) ──

class CorrectionSteps(BaseModel):
    sttTime: int = Field(description="STT 처리 시간 (ms)")
    correctionTime: int = Field(description="GPT 교정 처리 시간 (ms)")


class CorrectionSafeguard(BaseModel):
    userCanReview: bool = True
    optionsAvailable: List[str] = Field(
        default=["accept", "retry", "edit_manually"]
    )


class CorrectPronunciationResponse(BaseModel):
    callId: str
    originalText: str
    correctedText: str
    confidence: float = Field(ge=0.0, le=1.0)
    processingTime: int = Field(description="전체 처리 시간 (ms)")
    steps: CorrectionSteps
    safeguard: CorrectionSafeguard
    message: str
    timestamp: str  # ISO 8601 (UTC, Z)
