import argparse
import asyncio
import json
import os
import sys
import time
import wave
from dataclasses import dataclass
from typing import Optional, List, Tuple

from dotenv import load_dotenv
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

import websockets


@dataclass
class Metrics:
    start_ts: float
    first_msg_ts: Optional[float] = None
    first_interim_ts: Optional[float] = None
    first_final_ts: Optional[float] = None
    last_final_ts: Optional[float] = None
    interim_count: int = 0
    final_count: int = 0
    final_texts: List[str] = None

    def __post_init__(self):
        if self.final_texts is None:
            self.final_texts = []


def build_url(
    model: str,
    language: str,
    encoding: str,
    sample_rate: int,
    channels: int,
    interim_results: bool,
    endpointing_ms: int,
    vad_events: bool,
    punctuate: bool,
    smart_format: bool,
) -> str:
    params = {
        "model": model,
        "language": language,
        "encoding": encoding,
        "sample_rate": str(sample_rate),
        "channels": str(channels),
        "interim_results": "true" if interim_results else "false",
        "endpointing": str(endpointing_ms),
        "vad_events": "true" if vad_events else "false",
        "punctuate": "true" if punctuate else "false",
        "smart_format": "true" if smart_format else "false",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"wss://api.deepgram.com/v1/listen?{qs}"


def extract_transcript(dg_msg) -> Tuple[str, Optional[float], Optional[bool]]:
    """
    Deepgram streaming 메시지에서 transcript/confidence/is_final을 방어적으로 추출.
    - dg_msg: dict만 처리
    - dg_msg["channel"]이 dict 또는 list(채널 배열)일 수 있으므로 둘 다 지원
    """
    if not isinstance(dg_msg, dict):
        return "", None, None

    channel = dg_msg.get("channel")

    # ✅ case A: channel이 dict인 경우 (일반적인 형태)
    if isinstance(channel, dict):
        alts = channel.get("alternatives") or []

    # ✅ case B: channel이 list인 경우 (채널 배열 형태)
    elif isinstance(channel, list):
        # channel: [ {alternatives:[...]} , ... ] 또는 [ {...}, ... ]
        if channel and isinstance(channel[0], dict):
            alts = channel[0].get("alternatives") or []
        else:
            alts = []

    else:
        alts = []

    transcript = ""
    confidence = None

    if isinstance(alts, list) and alts:
        a0 = alts[0]
        if isinstance(a0, dict):
            transcript = a0.get("transcript") or ""
            confidence = a0.get("confidence")

    is_final = dg_msg.get("is_final")
    return transcript, confidence, is_final


async def keepalive_loop(ws, interval_sec: int, stop_evt: asyncio.Event):
    while not stop_evt.is_set():
        await asyncio.sleep(interval_sec)
        try:
            await ws.send(json.dumps({"type": "KeepAlive"}))
        except Exception:
            return


def iter_dict_events(payload):
    """
    payload가 dict/list(중첩 포함) 어떤 형태든 dict 이벤트만 yield.
    """
    if isinstance(payload, dict):
        yield payload
        return
    if isinstance(payload, list):
        for item in payload:
            yield from iter_dict_events(item)


async def recv_loop(ws, metrics: Metrics, stop_evt: asyncio.Event, verbose: bool):
    async def handle_one(msg: dict):
        if not isinstance(msg, dict):
            print("[WARN] non-dict event passed to handle_one:", type(msg), msg)
            return
        now = time.perf_counter()
        if metrics.first_msg_ts is None:
            metrics.first_msg_ts = now

        msg_type = msg.get("type")
        if msg_type == "Error":
            print("[Deepgram ERROR]", msg)
            stop_evt.set()
            return

        transcript, conf, is_final = extract_transcript(msg)
        if not transcript:
            return

        if is_final:
            metrics.final_count += 1
            metrics.last_final_ts = now
            if metrics.first_final_ts is None:
                metrics.first_final_ts = now
            metrics.final_texts.append(transcript)
            if verbose:
                print(f"[FINAL] {transcript}")
        else:
            metrics.interim_count += 1
            if metrics.first_interim_ts is None:
                metrics.first_interim_ts = now
            if verbose:
                print(f"[INTERIM] {transcript}")

    try:
        async for raw in ws:
            if stop_evt.is_set(): # 이미 종료 이벤트가 발생했다면 루프 종료
                break
                
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="ignore")

            try:
                payload = json.loads(raw)
            except Exception:
                continue

            # finally 제거: 여기서 이벤트를 set하면 안 됩니다.
            for msg in iter_dict_events(payload):
                await handle_one(msg) # handle_one 내부 로직 실행

    except Exception as e:
        print("[recv_loop exception]", repr(e))
    finally:
        # 모든 수신이 끝났을 때만 set
        stop_evt.set()


async def stream_wav(
    ws,
    wav_path: str,
    chunk_ms: int,
    realtime: bool,
    stop_evt: asyncio.Event,
):
    """
    WAV를 PCM 프레임으로 읽어서 chunk 단위로 WS 전송.
    realtime=True면 chunk_ms 만큼 sleep해서 '실시간' 속도로 보냄.
    """
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()  # bytes
        sample_rate = wf.getframerate()
        nframes = wf.getnframes()

        if sampwidth != 2:
            raise RuntimeError(f"WAV sample width must be 16-bit (2 bytes). Got: {sampwidth} bytes")

        bytes_per_frame = channels * sampwidth
        frames_per_chunk = int(sample_rate * chunk_ms / 1000)
        if frames_per_chunk <= 0:
            frames_per_chunk = 1

        total_duration_sec = nframes / float(sample_rate)
        print(f"[WAV] channels={channels}, sample_rate={sample_rate}, frames={nframes}, duration={total_duration_sec:.3f}s")
        print(f"[SEND] chunk_ms={chunk_ms}, frames_per_chunk={frames_per_chunk}, bytes_per_chunk≈{frames_per_chunk*bytes_per_frame}")

        sent_frames = 0
        t0 = time.perf_counter()

        while not stop_evt.is_set():
            data = wf.readframes(frames_per_chunk)
            if not data:
                break

            # 빈 바이트 방지
            if len(data) == 0:
                continue

            await ws.send(data)
            sent_frames += len(data) // bytes_per_frame

            if realtime:
                # "실시간 페이싱": 지금까지 보낸 오디오 길이만큼 시간이 흘렀어야 한다고 가정
                sent_audio_sec = sent_frames / float(sample_rate)
                elapsed = time.perf_counter() - t0
                sleep_sec = sent_audio_sec - elapsed
                if sleep_sec > 0:
                    await asyncio.sleep(sleep_sec)

        # 끝나면 Finalize 요청
        try:
            await ws.send(json.dumps({"type": "Finalize"}))
        except Exception:
            pass


async def run(args):
    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not api_key:
        print("ERROR: DEEPGRAM_API_KEY is empty. Set env var or .env via your settings loader.")
        sys.exit(2)

    # WAV 정보 읽어서 sample_rate/channels 확인 (실제 전송은 raw PCM이므로 query에 정확히 넣어야 함)
    with wave.open(args.wav, "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        if sampwidth != 2:
            raise RuntimeError("Only 16-bit PCM WAV is supported for this test script.")
        if args.channels is not None and args.channels != channels:
            print(f"WARNING: --channels={args.channels} but wav has channels={channels}. Using wav's channels.")
        if args.sample_rate is not None and args.sample_rate != sample_rate:
            print(f"WARNING: --sample_rate={args.sample_rate} but wav has sample_rate={sample_rate}. Using wav's sample_rate.")

    url = build_url(
        model=args.model,
        language=args.language,
        encoding="linear16",  # WAV에서 PCM 16-bit raw만 보내므로 linear16
        sample_rate=sample_rate,
        channels=channels,
        interim_results=not args.no_interim,
        endpointing_ms=args.endpointing,
        vad_events=not args.no_vad,
        punctuate=not args.no_punctuate,
        smart_format=not args.no_smart_format,
    )

    headers = [("Authorization", f"Token {api_key}")]
    print("[Deepgram] URL:", url)
    print("[Deepgram] realtime pacing:", args.realtime)

    metrics = Metrics(start_ts=time.perf_counter())
    stop_evt = asyncio.Event()

    try:
        async with websockets.connect(
            url,
            additional_headers=headers,  # websockets 12+
            ping_interval=None,
        ) as ws:
            keepalive_task = asyncio.create_task(keepalive_loop(ws, interval_sec=5, stop_evt=stop_evt))
            recv_task = asyncio.create_task(recv_loop(ws, metrics, stop_evt, verbose=args.verbose))

            # 송신
            await stream_wav(
                ws,
                wav_path=args.wav,
                chunk_ms=args.chunk_ms,
                realtime=args.realtime,
                stop_evt=stop_evt,
            )

            # finalize 이후 잠깐 더 기다리며 결과 수신
            # (endpointing/모델에 따라 마지막 final이 조금 늦게 올 수 있음)
            await asyncio.sleep(args.final_wait_sec)
            stop_evt.set()

            keepalive_task.cancel()
            recv_task.cancel()

    except TypeError:
        # websockets<=11 호환
        async with websockets.connect(
            url,
            extra_headers=dict(headers),
            ping_interval=None,
        ) as ws:
            keepalive_task = asyncio.create_task(keepalive_loop(ws, interval_sec=5, stop_evt=stop_evt))
            recv_task = asyncio.create_task(recv_loop(ws, metrics, stop_evt, verbose=args.verbose))

            await stream_wav(
                ws,
                wav_path=args.wav,
                chunk_ms=args.chunk_ms,
                realtime=args.realtime,
                stop_evt=stop_evt,
            )

            await asyncio.sleep(args.final_wait_sec)
            stop_evt.set()

            keepalive_task.cancel()
            recv_task.cancel()

    # ----- 결과 출력 -----
    end_ts = time.perf_counter()

    with wave.open(args.wav, "rb") as wf:
        duration_sec = wf.getnframes() / float(wf.getframerate())

    total_ms = (end_ts - metrics.start_ts) * 1000
    ttfb_ms = (metrics.first_msg_ts - metrics.start_ts) * 1000 if metrics.first_msg_ts else None
    first_interim_ms = (metrics.first_interim_ts - metrics.start_ts) * 1000 if metrics.first_interim_ts else None
    first_final_ms = (metrics.first_final_ts - metrics.start_ts) * 1000 if metrics.first_final_ts else None
    last_final_ms = (metrics.last_final_ts - metrics.start_ts) * 1000 if metrics.last_final_ts else None
    rtf = (end_ts - metrics.start_ts) / duration_sec if duration_sec > 0 else None

    print("\n=== Metrics ===")
    print(f"audio_duration_sec: {duration_sec:.3f}")
    print(f"total_elapsed_ms:   {total_ms:.1f}")
    print(f"RTF:                {rtf:.3f}" if rtf is not None else "RTF: N/A")

    print(f"TTFB_ms:            {ttfb_ms:.1f}" if ttfb_ms is not None else "TTFB_ms: N/A")
    print(f"first_interim_ms:   {first_interim_ms:.1f}" if first_interim_ms is not None else "first_interim_ms: N/A")
    print(f"first_final_ms:     {first_final_ms:.1f}" if first_final_ms is not None else "first_final_ms: N/A")
    print(f"last_final_ms:      {last_final_ms:.1f}" if last_final_ms is not None else "last_final_ms: N/A")

    print(f"interim_count:      {metrics.interim_count}")
    print(f"final_count:        {metrics.final_count}")

    final_text = " ".join(t.strip() for t in metrics.final_texts if t.strip()).strip()
    print("\n=== Final Text ===")
    print(final_text if final_text else "(empty)")


def main():
    p = argparse.ArgumentParser(description="Measure Deepgram Live streaming latency (TTFB/RTF) using a WAV file.")
    p.add_argument("--wav", required=True, help="Path to 16-bit PCM WAV file")
    p.add_argument("--model", default="nova-3", help="Deepgram model (default: nova-3)")
    p.add_argument("--language", default="ko", help="Language code (default: ko)")

    p.add_argument("--chunk-ms", type=int, default=75, help="Chunk size in ms (default: 75)")
    p.add_argument("--realtime", action="store_true", help="Pace sending in real-time (recommended for realism)")

    p.add_argument("--endpointing", type=int, default=300, help="Endpointing in ms (default: 300)")
    p.add_argument("--no-interim", action="store_true", help="Disable interim results")
    p.add_argument("--no-vad", action="store_true", help="Disable vad_events")
    p.add_argument("--no-punctuate", action="store_true", help="Disable punctuate")
    p.add_argument("--no-smart-format", action="store_true", help="Disable smart_format")

    p.add_argument("--final-wait-sec", type=float, default=2.0, help="Wait seconds after finalize (default: 2.0)")
    p.add_argument("--verbose", action="store_true", help="Print interim/final transcripts as they arrive")

    # optional overrides (not used; script reads from wav)
    p.add_argument("--sample-rate", type=int, default=None, help="(Ignored) Use WAV sample_rate")
    p.add_argument("--channels", type=int, default=None, help="(Ignored) Use WAV channels")

    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
