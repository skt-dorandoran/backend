from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from schemas.voice_schema import UploadVoiceSampleResponse
from services.voice_service import VoiceService

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
voice_service = VoiceService()


@router.post("/upload-samples", response_model=UploadVoiceSampleResponse)
async def upload_voice_samples(
    sampleName: str = Form(...),
    audioFile: UploadFile = File(...),
    audioFormat: str = Form(...),
    duration: int = Form(...),
    sampleRate: int = Form(...),
):
    # print("DEBUG audioFormat repr:", repr(audioFormat))
    # print("DEBUG filename:", audioFile.filename)
    # print("DEBUG content_type:", audioFile.content_type)
    # 명세 준수: multipart/form-data의 Form Fields 그대로 받음
    # (추가 필드 요구/추가 응답 없음)
    try:
        return await voice_service.upload_sample(
            sample_name=sampleName,
            audio_file=audioFile,
            audio_format=audioFormat,
            duration=duration,
            sample_rate=sampleRate,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
