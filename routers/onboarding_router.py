from fastapi import APIRouter, UploadFile, File, HTTPException
from starlette.datastructures import UploadFile as StarletteUploadFile, Headers

from services.onboarding_service import OnboardingService
from services.stt_service import transcribe_file_batch  # ✅ 배치 STT 함수 사용

router = APIRouter(prefix="/api/v1/onboarding/pronunciation", tags=["Onboarding"])
svc = OnboardingService()


@router.post("/sessions")
async def create_session(userId: str):
    prompt = "발음 때문인지 중국인 외국인으로 오해받아요 포트폴리오 덕분에 연락 많이 왔었어요 이력서에 기재해뒀던 청각장애 부분을 보고 확인했냐고 물어봤어요"
    return svc.create_session(user_id=userId, prompt_text=prompt)


@router.post("/sessions/{sessionId}/upload")
async def upload_audio(sessionId: str, audio: UploadFile = File(...)):
    return await svc.upload_audio(sessionId, audio)


@router.post("/sessions/{sessionId}/finalize")
async def finalize(sessionId: str, language: str | None = None, model: str | None = None):
    # 1) 세션 조회 및 저장된 오디오 경로 확보
    sess = svc._sessions.get(sessionId)
    if not sess:
        raise HTTPException(status_code=404, detail="onboarding session not found")
    audio_path = sess.get("audioPath")
    if not audio_path:
        raise HTTPException(status_code=400, detail="no audio uploaded")

    # 2) 저장된 파일을 UploadFile 형태로 래핑해서 기존 transcribe_file_batch 재사용
    #    - content_type은 확장자 기반으로 간단 매핑
    ext = audio_path.split(".")[-1].lower()
    content_type_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    with open(audio_path, "rb") as f:
        # Starlette UploadFile은 file-like object를 받음
        headers = Headers({"content-type": content_type})  # ✅ 여기서 content-type 주입
        wrapped = StarletteUploadFile(
            filename=f"onboarding.{ext}",
            file=f,
            headers=headers
        )
        done = await transcribe_file_batch(wrapped, language=language, model=model)

        recognized_text = done.transcribedText

    # 3) persona 산출/저장 로직은 서비스 finalize를 그대로 쓰고 싶다면,
    #    OnboardingService.finalize를 "recognized_text를 직접 주입" 가능하게 바꾸는 게 깔끔함.
    #    여기서는 가장 단순하게 서비스에 helper를 하나 추가했다고 가정:
    result = svc.finalize_with_recognized_text(sessionId, recognized_text)
    return result
