from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal, Optional

from core.settings import settings
from schemas.ai_schema import (
    GenerateResponseRequest,
    GenerateResponseResponse,
    CorrectSpeechRequest,
    CorrectSpeechResponse,
)
from services.ai_service import AIService
from services.tts_service import ElevenTTSService, ElevenTTSError

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
ai_service = AIService()

tts_service = ElevenTTSService(
    api_key=settings.ELEVENLABS_API_KEY,
    model_id=settings.ELEVENLABS_TTS_MODEL_ID,
)


@router.post("/generate-response", response_model=GenerateResponseResponse)
async def generate_response(request: GenerateResponseRequest):
    try:
        return await ai_service.generate_response(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correct-speech", response_model=CorrectSpeechResponse)
async def correct_speech(request: CorrectSpeechRequest):
    try:
        return await ai_service.correct_speech(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SynthesizeRequest(BaseModel):
    callId: str
    text: str = Field(min_length=1)
    voiceId: str = Field(..., min_length=1, description="ElevenLabs Voice ID 필수")
    sourceType: Literal["ai_response", "corrected", "typed"]

@router.post("/synthesize-response")
async def synthesize_response(req: SynthesizeRequest):
    # print(f"DEBUG: voiceId received: '{req.voiceId}'")

    if not req.text.strip():
        raise HTTPException(status_code=400, detail="텍스트 필드는 필수입니다")

    try:
        wav_bytes, m = await tts_service.synthesize_wav_with_metrics(
            voice_id=req.voiceId,
            text=req.text,
        )
    except ElevenTTSError as e:
        msg = str(e)
        if "voice" in msg.lower() and "not found" in msg.lower():
            raise HTTPException(status_code=404, detail="음성 클론 모델을 찾을 수 없습니다")
        raise HTTPException(status_code=400, detail=msg)
    except Exception:
        raise HTTPException(status_code=500, detail="음성 합성 중 오류가 발생했습니다")

    headers = {
        "Content-Disposition": 'attachment; filename="response_audio.wav"',
        "X-Call-Id": req.callId,
        "X-Duration": str(m["duration_ms"]),
        "X-Sample-Rate": str(m["sample_rate"]),
        "X-Processing-Time": str(m["processing_ms"]),
        "X-Model-Load-Time": str(m["model_load_ms"]),
        "X-TTS-Time": str(m["tts_ms"]),
    }

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers=headers,
    )
