import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas.ai_schema import (
    ConversationMessage,
    CorrectPronunciationResponse,
    GenerateResponseRequest,
    GenerateResponseResponse,
)
from services.ai_service import AIService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
ai_service = AIService()


@router.post("/generate-response", response_model=GenerateResponseResponse)
async def generate_response(request: GenerateResponseRequest):
    try:
        return await ai_service.generate_response(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correct-pronunciation", response_model=CorrectPronunciationResponse)
async def correct_pronunciation(
    callId: str = Form(...),
    audioFile: UploadFile = File(...),
    audioFormat: str = Form(...),
    sampleRate: int = Form(16000),
    duration: int = Form(0),
    conversationHistory: str = Form("[]"),
):
    try:
        history = [
            ConversationMessage(**msg)
            for msg in json.loads(conversationHistory)
        ]
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"conversationHistory 파싱 실패: {e}")

    audio_bytes = await audioFile.read()

    try:
        return await ai_service.correct_pronunciation(
            call_id=callId,
            audio_bytes=audio_bytes,
            audio_format=audioFormat,
            conversation_history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
