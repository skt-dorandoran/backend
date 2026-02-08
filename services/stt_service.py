import asyncio
from email.mime import text
import json
import time
from datetime import datetime, timezone
from typing import AsyncIterator, Optional, Tuple

from fastapi import UploadFile, WebSocket
from fastapi.responses import StreamingResponse

from clients.client import DeepgramStreamingClient
from schemas.stt_schema import StreamEvent, TranscribeDoneResponse
from core.settings import settings


from pykospacing import Spacing

spacing = Spacing()


def apply_korean_spacing(text: str) -> str:
    """한국어 띄어쓰기 보정"""
    if not text.strip():
        return text
    try:
        return spacing(text)
    except Exception as e:
        print(f"띄어쓰기 보정 실패: {e}")
        return text


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_text_and_confidence(dg_msg: any):
    # dg_msg가 list면 첫 원소
    if isinstance(dg_msg, list):
        dg_msg = dg_msg[0] if dg_msg else {}

    # dict 아니면 스킵
    if not isinstance(dg_msg, dict):
        return "", None, False, False, None, None

    # transcript 계열 이벤트가 아닐 수도 있음 → channel이 dict인지 확인
    channel = dg_msg.get("channel")
    if isinstance(channel, list):
        channel = channel[0] if channel else None
    if not isinstance(channel, dict):
        # 여기서 그냥 "텍스트 없음" 처리 (VAD/metadata 등)
        is_final = bool(dg_msg.get("is_final", False))
        speech_final = bool(dg_msg.get("speech_final", False))
        return "", None, is_final, speech_final, dg_msg.get("start"), dg_msg.get("duration")

    alts = channel.get("alternatives") or []
    transcript = ""
    confidence = None
    if isinstance(alts, list) and alts:
        a0 = alts[0] if isinstance(alts[0], dict) else {}
        transcript = a0.get("transcript") or ""
        confidence = a0.get("confidence")

    is_final = bool(dg_msg.get("is_final", False))
    speech_final = bool(dg_msg.get("speech_final", False))
    start = dg_msg.get("start")
    duration = dg_msg.get("duration")
    return transcript, confidence, is_final, speech_final, start, duration


def _sse_pack(event_name: str, data: dict) -> str:
    # SSE 포맷: event: <name>\n data: <json>\n\n
    return f"event: {event_name}\n" + f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def transcribe_file_sse(
    file: UploadFile,
    *,
    language: Optional[str] = None,
    model: Optional[str] = None,
) -> StreamingResponse:
    """
    업로드된 파일을 chunk로 읽어 Deepgram Live WS로 스트리밍 전송하면서
    transcript를 SSE로 즉시 반환.
    """
    if not settings.DEEPGRAM_API_KEY:
        async def err_gen():
            yield _sse_pack("error", StreamEvent(type="error", text="DEEPGRAM_API_KEY is not set").model_dump())
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    dg_language = language or settings.DEEPGRAM_LANGUAGE
    dg_model = model or settings.DEEPGRAM_MODEL

    start = time.perf_counter()
    assembled_final = []
    best_conf = 0.0

    # 파일 업로드는 보통 wav/mp3/webm 등 "컨테이너"라 raw PCM 옵션 없이 보냄(Deepgram이 디코딩)
    async def event_generator() -> AsyncIterator[str]:
        nonlocal best_conf

        async with DeepgramStreamingClient(
            settings.DEEPGRAM_API_KEY,
            model=dg_model,
            language=dg_language,
            # encoding/sample_rate 생략 => 파일 컨테이너로 처리(Deepgram 자동 디코드)
            encoding=None,
            sample_rate=None,
            endpointing_ms=settings.DEEPGRAM_ENDPOINTING_MS,
            interim_results=True,
            vad_events=True,
        ) as dg:

            # keepalive (파일 업로드는 계속 오디오가 들어오니 필수는 아니지만 안전장치)
            keepalive_task = asyncio.create_task(_keepalive_loop(dg, interval_sec=5))

            # Deepgram 수신 loop
            recv_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)

            async def recv_loop():
                try:
                    async for msg in dg.recv_events():
                        # 큐가 가득 차면 최신 우선(가장 오래된 것 버림)
                        if recv_queue.full():
                            try:
                                recv_queue.get_nowait()
                            except Exception:
                                pass
                        await recv_queue.put(msg)
                except Exception as e:
                    await recv_queue.put({"_error": str(e)})

            recv_task = asyncio.create_task(recv_loop())

            # 파일 송신 loop (chunk로 읽어서 바로 전송)
            # 64KB 정도 chunk가 무난. (파일 -> 네트워크 -> Deepgram)
            try:
                yield _sse_pack("meta", StreamEvent(type="meta", raw={"message": "stream_start"}).model_dump())

                while True:
                    chunk = await file.read(64 * 1024)
                    if not chunk:
                        break
                    await dg.send_audio(chunk)

                    # 송신 중간중간 수신된 결과를 "즉시" drain
                    drained = 0
                    while not recv_queue.empty() and drained < 50:
                        dg_msg = await recv_queue.get()
                        if "_error" in dg_msg:
                            yield _sse_pack("error", StreamEvent(type="error", text=dg_msg["_error"], raw=dg_msg).model_dump())
                            return

                        transcript, conf, is_final, speech_final, start, duration = _extract_text_and_confidence(dg_msg)
                        if transcript:
                            if conf is not None:
                                best_conf = max(best_conf, float(conf))
                            if is_final:
                                assembled_final.append(transcript)
                                ev = StreamEvent(type="final", text=transcript, confidence=conf, is_final=True, raw=dg_msg)
                                yield _sse_pack("final", ev.model_dump())
                            else:
                                ev = StreamEvent(type="interim", text=transcript, confidence=conf, is_final=False, raw=dg_msg)
                                yield _sse_pack("interim", ev.model_dump())
                        drained += 1

                # 파일 끝: Deepgram에 finalize 요청 후 남은 결과 수신
                await dg.send_finalize()

                # finalize 이후 잠깐 결과를 더 받는다(짧게)
                end_deadline = time.perf_counter() + 2.0
                while time.perf_counter() < end_deadline:
                    try:
                        dg_msg = await asyncio.wait_for(recv_queue.get(), timeout=0.25)
                    except asyncio.TimeoutError:
                        continue

                    if "_error" in dg_msg:
                        yield _sse_pack("error", StreamEvent(type="error", text=dg_msg["_error"], raw=dg_msg).model_dump())
                        return

                    transcript, conf, is_final, speech_final, start, duration = _extract_text_and_confidence(dg_msg)
                    if transcript:
                        if conf is not None:
                            best_conf = max(best_conf, float(conf))
                        if is_final:
                            assembled_final.append(transcript)
                            yield _sse_pack("final", StreamEvent(type="final", text=transcript, confidence=conf, is_final=True, raw=dg_msg).model_dump())
                        else:
                            yield _sse_pack("interim", StreamEvent(type="interim", text=transcript, confidence=conf, is_final=False, raw=dg_msg).model_dump())

                # done summary
                processing_ms = int((time.perf_counter() - start) * 1000)
                final_text = " ".join(t.strip() for t in assembled_final if t.strip()).strip()
                final_text = apply_korean_spacing(final_text)

                done = TranscribeDoneResponse(
                    transcribedText=final_text,
                    confidence=float(best_conf or 0.0),
                    duration=0,  # 파일 길이(ms)는 컨테이너 파싱이 필요. 여기서는 0으로 두고 필요 시 확장
                    processingTime=processing_ms,
                    message="음성이 성공적으로 텍스트로 변환되었습니다",
                    timestamp=_utc_now_iso(),
                )
                yield _sse_pack("done", StreamEvent(type="done", raw=done.model_dump()).model_dump())

            finally:
                keepalive_task.cancel()
                recv_task.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _keepalive_loop(dg: DeepgramStreamingClient, interval_sec: int = 5):
    while True:
        await asyncio.sleep(interval_sec)
        try:
            await dg.send_keepalive()
        except Exception:
            return


# -----------------------------
# WebSocket 실시간 스트리밍용
# -----------------------------
async def stream_transcribe_ws(
    client_ws: WebSocket,
    *,
    encoding: str = "linear16",
    sample_rate: int = 16000,
    channels: int = 1,
    language: Optional[str] = None,
    model: Optional[str] = None,
):
    """
    클라이언트(=Kotlin)가 binary로 오디오 프레임을 보내면,
    Deepgram Live WS로 즉시 relay하고 transcript 이벤트를 다시 client로 push.
    """
    # print("stream_transcribe_ws entered")
    await client_ws.accept()
    # print("accepted")

    # 세션 기준 타이머
    session_start = time.perf_counter()

    if not settings.DEEPGRAM_API_KEY:
        await client_ws.send_json(StreamEvent(type="error", text="DEEPGRAM_API_KEY is not set").model_dump())
        await client_ws.close()
        return
    
    # Start Handshake
    try:
        # 첫 메시지는 반드시 텍스트(JSON)여야 함
        first = await client_ws.receive()
        if first["type"] == "websocket.disconnect":
            return

        if not first.get("text"):
            await client_ws.send_json({
                "type": "error",
                "text": "First message must be JSON text: {\"sampleRate\":16000} (or \"16000\")"
            })
            await client_ws.close()
            return

        raw_text = first["text"].strip()

        # 1) JSON 오브젝트 형태: {"sampleRate": 16000, "silenceThreshold": 8.0}
        sr = None
        silence_threshold = None
        try:
            obj = json.loads(raw_text)
            if isinstance(obj, dict):
                sr = obj.get("sampleRate")
                silence_threshold = obj.get("silenceThreshold")
            elif isinstance(obj, (int, float)):
                # 2) 숫자 단독 형태: 16000 (JSON number)
                sr = obj
        except Exception:
            # 3) 그냥 문자열 숫자: "16000"
            if raw_text.isdigit():
                sr = int(raw_text)

        if not isinstance(sr, (int, float)) or sr <= 0:
            await client_ws.send_json({
                "type": "error",
                "text": "Invalid sampleRate. Example: {\"sampleRate\":16000, \"silenceThreshold\":8.0}"
            })
            await client_ws.close()
            return

        sample_rate = int(sr)

        # silenceThreshold 검증 (선택적 파라미터)
        if silence_threshold is not None:
            if not isinstance(silence_threshold, (int, float)) or silence_threshold < 5.0:
                await client_ws.send_json({
                    "type": "error",
                    "text": "silenceThreshold must be >= 5.0 seconds"
                })
                await client_ws.close()
                return
            silence_threshold = float(silence_threshold)

    except Exception as e:
        await client_ws.send_json({"type": "error", "text": f"Failed to start transcription: {e}"})
        await client_ws.close()
        return

    dg_language = language or settings.DEEPGRAM_LANGUAGE
    dg_model = model or settings.DEEPGRAM_MODEL

    async with DeepgramStreamingClient(
        settings.DEEPGRAM_API_KEY,
        model=dg_model,
        language=dg_language,
        encoding=encoding,
        sample_rate=sample_rate,
        channels=channels,
        interim_results=True,
        endpointing_ms=settings.DEEPGRAM_ENDPOINTING_MS,
        vad_events=True,
    ) as dg:

        stop_event = asyncio.Event()

        # 침묵 감지 상태 (silenceThreshold가 설정된 경우에만 사용)
        last_speech_time = time.perf_counter() if silence_threshold else None
        silence_detected_sent = False

        async def silence_monitor():
            """침묵 감지 모니터링 태스크 (silenceThreshold 설정 시에만 실행)"""
            nonlocal last_speech_time, silence_detected_sent

            if silence_threshold is None:
                return

            try:
                while not stop_event.is_set():
                    await asyncio.sleep(1.0)  # 1초마다 체크

                    if last_speech_time is None:
                        continue

                    silence_duration = time.perf_counter() - last_speech_time

                    # 침묵이 threshold를 초과하고, 아직 이벤트를 보내지 않았으면
                    if silence_duration >= silence_threshold and not silence_detected_sent:
                        await client_ws.send_json({
                            "type": "silence_detected",
                            "silenceDuration": round(silence_duration, 2),
                            "timestamp": _utc_now_iso(),
                        })
                        silence_detected_sent = True
            except Exception as e:
                print(f"[Silence Monitor 에러] {e}")

        async def client_to_dg():
            try:
                while not stop_event.is_set():
                    msg = await client_ws.receive()
                    if msg["type"] == "websocket.disconnect":
                        break

                    if "bytes" in msg and msg["bytes"]:
                        print(f"DEBUG: Received {len(msg['bytes'])} bytes from client")
                        await dg.send_audio(msg["bytes"])
                    elif "text" in msg:
                        # 컨트롤 메시지(예: {"type":"finalize"} )
                        try:
                            obj = json.loads(msg["text"])
                        except Exception:
                            obj = {}
                        if obj.get("type") == "finalize":
                            await dg.send_finalize()
                        elif obj.get("type") == "keepalive":
                            await dg.send_keepalive()
            except Exception as e:
                print(f"[Client -> DG 에러] {e}")
            finally:
                stop_event.set()

        async def dg_to_client():
            nonlocal last_speech_time, silence_detected_sent

            try:
                async for dg_msg in dg.recv_events():
                    if stop_event.is_set():
                        break

                    text, conf, is_final, speech_final, start, duration = _extract_text_and_confidence(dg_msg)

                    # 침묵 감지: 음성 활동이 감지되면 타이머 리셋
                    if silence_threshold is not None and text.strip():
                        last_speech_time = time.perf_counter()
                        silence_detected_sent = False  # 새로운 음성이 감지되면 플래그 리셋

                    if not text.strip():
                        continue

                    # 서버 기준 시간/처리시간
                    ts = _utc_now_iso()
                    proc_ms = int((time.perf_counter() - session_start) * 1000)

                    if is_final:
                        corrected_text = apply_korean_spacing(text)
                        await client_ws.send_json({
                            "type": "final",
                            "text": corrected_text,
                            "confidence": conf,
                            "speech_final": speech_final,
                            "start": start,
                            "duration": duration,
                            "timestamp": ts,
                            "processingTime": proc_ms,
                        })
                    else:
                        await client_ws.send_json({
                            "type": "interim",
                            "text": text,
                            "confidence": conf,
                            "start": start,
                            "duration": duration,
                            "timestamp": ts,
                            "processingTime": proc_ms,
                        })
            except Exception as e:
                print(f"[DG -> Client 에러] {e}")
            finally:
                stop_event.set()


        keepalive_task = asyncio.create_task(_keepalive_loop(dg, interval_sec=5))
        silence_task = asyncio.create_task(silence_monitor()) if silence_threshold else None

        try:
            tasks = [
                asyncio.create_task(client_to_dg()),
                asyncio.create_task(dg_to_client())
            ]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stop_event.set()
            keepalive_task.cancel()
            if silence_task:
                silence_task.cancel()


# =============================
# Local Test Functions
# =============================

from clients.rest import transcribe_prerecorded

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_best_alt(dg_json: dict):
    """
    Deepgram prerecorded 응답에서 transcript/confidence 추출(방어적)
    """
    # 대표 스키마: results.channels[0].alternatives[0]
    results = dg_json.get("results") or {}
    channels = results.get("channels") or []
    if not channels:
        return "", 0.0

    alts = (channels[0] or {}).get("alternatives") or []
    if not alts:
        return "", 0.0

    alt0 = alts[0] or {}
    text = alt0.get("transcript") or ""
    conf = alt0.get("confidence")
    try:
        conf = float(conf) if conf is not None else 0.0
    except Exception:
        conf = 0.0
    return text, conf


async def transcribe_file_batch(
    file: UploadFile,
    *,
    language: Optional[str] = None,
    model: Optional[str] = None,
) -> TranscribeDoneResponse:
    file_bytes = await file.read()

    # content-type이 비어있을 수 있어 fallback
    content_type = file.content_type or "application/octet-stream"

    dg_json = await transcribe_prerecorded(
        file_bytes,
        content_type=content_type,
        model=model,
        language=language,
    )

    text, conf = _extract_best_alt(dg_json)
    text = apply_korean_spacing(text)
    processing_ms = int(dg_json.get("_processing_ms") or 0)

    # duration(ms)는 파일 파싱이 필요(여기선 0). 필요하면 wav 헤더 파싱을 추가로 붙이면 됨.
    return TranscribeDoneResponse(
        transcribedText=text,
        confidence=conf,
        duration=0,
        processingTime=processing_ms,
        message="음성이 성공적으로 텍스트로 변환되었습니다",
        timestamp=_utc_now_iso(),
    )