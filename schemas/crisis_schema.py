from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class ComprehensionCheckRequest(BaseModel):
    callId: str = Field(..., description="통화 고유 ID")
    text: str = Field(..., description="STT로 변환된 텍스트")
    timestamp: str = Field(..., description="STT 결과 생성 시각 (ISO 8601)")
    isFinal: bool = Field(default=True, description="최종 결과 여부")


class ComprehensionCheckResponse(BaseModel):
    status: Literal["ok", "monitoring", "alert", "error"]
    callId: str
    keywordMatched: bool
    matchedKeywords: Optional[List[str]] = None
    duplicateDetected: Optional[bool] = None
    failureCount: int
    threshold: int
    enableAiCorrection: Optional[bool] = None
    timestamp: str  # ISO 8601 (UTC, Z)


class ComprehensionCheckErrorResponse(BaseModel):
    status: Literal["error"]
    code: str
    message: str
