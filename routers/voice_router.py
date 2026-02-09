from fastapi import APIRouter, File, Form, Path, Body, UploadFile, HTTPException

from schemas.voice_schema import UploadVoiceSampleResponse, VoiceDeleteRequest, VoiceDeleteResponse
from services.voice_service import VoiceService

from core.settings import settings
from services.clone_service import ElevenLabsService
from typing import List

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
voice_service = VoiceService()


_service = ElevenLabsService(api_key=settings.ELEVENLABS_API_KEY)


@router.post("/upload-samples", response_model=UploadVoiceSampleResponse)
async def upload_voice_samples(
    sampleName: str = Form(...),
    audioFile: UploadFile = File(...),
    audioFormat: str = Form(...),
    duration: int = Form(...),
    sampleRate: int = Form(...),
):
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


_service = ElevenLabsService(api_key=settings.ELEVENLABS_API_KEY)


@router.post("/clone")
async def create_voice_clone(
    modelName: str = Form(..., description="생성할 보이스 이름"),
    modelFile: List[UploadFile] = File(..., description="m4a/wav/mp3 등 음성 샘플 파일들 (여러 개 가능)"),
):
    if not modelFile:
        raise HTTPException(status_code=400, detail="modelFile is required")

    # 파일 바이트 읽기
    file_bytes_list: List[bytes] = []
    for f in modelFile:
        data = await f.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"Empty file: {f.filename}")
        file_bytes_list.append(data)

    try:
        voice_id = _service.create_voice_clone(name=modelName, file_bytes_list=file_bytes_list)
        return {
            "voiceId": voice_id,
            "modelName": modelName,
            "fileCount": len(modelFile),
        }
    except RuntimeError as e:
        # 구독/권한 문제(예: can_not_use_instant_voice_cloning)도 여기로 들어옴
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/voice-delete/{voiceId}", response_model=VoiceDeleteResponse)
async def delete_voice(
    voiceId: str = Path(..., description="삭제할 음성 모델 ID"),
    body: VoiceDeleteRequest = Body(default=VoiceDeleteRequest()),
):
    # body가 들어오면 path와 일치하는지 검증 (명세 충족 + 안전장치)
    if body.voiceId is not None and body.voiceId != voiceId:
        raise HTTPException(
            status_code=400,
            detail="voiceId in body must match voiceId in path",
        )

    result = await voice_service.delete_voice(voiceId)

    # ElevenLabs는 보통 {"status":"ok"} :contentReference[oaicite:4]{index=4}
    status = result.get("status", "ok")
    return VoiceDeleteResponse(status=status)
