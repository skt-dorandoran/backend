from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any


class TranscribeDoneResponse(BaseModel):
    transcribedText: str
    confidence: float = Field(ge=0.0, le=1.0)
    duration: int  # ms (가능하면 측정/추정)
    processingTime: int  # ms
    message: str
    timestamp: str  # ISO 8601 (UTC)


class StreamEvent(BaseModel):
    """
    SSE/WS로 보내는 이벤트(권장 포맷)
    """
    type: Literal["interim", "final", "meta", "error", "done", "silence_detected"]
    text: Optional[str] = None
    confidence: Optional[float] = None
    is_final: Optional[bool] = None
    raw: Optional[Dict[str, Any]] = None
