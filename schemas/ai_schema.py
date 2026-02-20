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
    tone: Literal["friendly", "formal", "casual", "professional", "polite"]
    priority: int = Field(ge=1, le=3)


class GenerateResponseResponse(BaseModel):
    callId: str
    responses: List[ResponseItem]
    generatedAt: str  # ISO 8601 (UTC, Z)
    processingTime: float = Field(description="처리 시간 (초)")


class CorrectSpeechRequest(BaseModel):
    callId: str = Field(..., min_length=1, description="통화 고유 ID")
    rawText: str = Field(..., min_length=1, description="WhisperX STT 결과 (깨진 발음)")
    conversationHistory: List[ConversationMessage] = Field(default_factory=list, description="최근 3~5턴 대화 맥락")
    phoneNumber: Optional[str] = None


class CorrectSpeechResponse(BaseModel):
    callId: str
    correctedText: str = Field(description="GPT-4o가 교정한 텍스트")
    rawText: str = Field(description="입력 원본 (디버깅용)")
    confidence: float = Field(ge=0.0, le=1.0, description="교정 신뢰도")
    processingTime: int = Field(description="처리 시간 (ms)")
    message: str
    timestamp: str = Field(description="ISO 8601 KST")
