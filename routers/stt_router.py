from fastapi import APIRouter, UploadFile, File, Query, WebSocket

from services.stt_service import transcribe_file_sse, stream_transcribe_ws

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Query(default=None),
    model: str | None = Query(default=None),
):
    """
    docs/개발 편의용: 업로드된 파일을 Deepgram Live로 스트리밍 전송하고,
    결과를 SSE로 즉시 반환(text/event-stream).
    """
    return await transcribe_file_sse(file, language=language, model=model)


@router.websocket("/transcribe/ws")
async def transcribe_ws(
    websocket: WebSocket,
    encoding: str = Query(default="linear16"),
    sample_rate: int = Query(default=16000),
    channels: int = Query(default=1),
    language: str | None = Query(default=None),
    model: str | None = Query(default=None),
):
    """
    실시간 스트리밍: 클라이언트가 binary frame으로 오디오를 보내면
    transcript를 즉시 WS로 push
    """
    # print("WS route hit")
    await stream_transcribe_ws(
        websocket,
        encoding=encoding,
        sample_rate=sample_rate,
        channels=channels,
        language=language,
        model=model,
    )


# =============================
# Local Test Functions
# =============================

from services.stt_service import transcribe_file_batch

@router.post("/transcribe/local")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Query(default=None),
    model: str | None = Query(default=None),
):
    return await transcribe_file_batch(file, language=language, model=model)