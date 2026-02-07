import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

### python tools/test_synthesize_wav.py --voice-id YOUR_VOICE_ID --play


def play_wav_file(path: Path) -> None:
    """
    OS 기본 플레이어로 재생 (추가 패키지 없이 가장 안정).
    """
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')  # noqa: S605
    else:
        os.system(f'xdg-open "{path}"')  # noqa: S605


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/api/v1/ai/synthesize-response")
    p.add_argument("--call-id", default="call_test_001")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--text", default="안녕하세요. 이 문장을 음성으로 합성합니다.")
    p.add_argument("--source-type", default="ai_response", choices=["ai_response", "corrected", "typed"])
    p.add_argument("--out", default="response_audio.wav")
    p.add_argument("--play", action="store_true", help="다운로드 완료 후 자동 재생")
    args = p.parse_args()

    payload = {
        "callId": args.call_id,
        "text": args.text,
        "voiceId": args.voice_id,
        "sourceType": args.source_type,
    }

    out_path = Path(args.out).resolve()
    t0 = time.perf_counter()

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", args.url, json=payload) as r:
            if r.status_code != 200:
                try:
                    print("Error JSON:", r.json())
                except Exception:
                    print("Error text:", await r.aread())
                return

            # --- 메타데이터 헤더 출력 ---
            print("=== Response headers ===")
            for k in [
                "content-type",
                "content-disposition",
                "x-call-id",
                "x-duration",
                "x-sample-rate",
                "x-processing-time",
                "x-model-load-time",
                "x-tts-time",
                "content-length",
            ]:
                if k in r.headers:
                    print(f"{k}: {r.headers[k]}")
            print("========================\n")

            # --- 스트리밍으로 파일 저장 ---
            bytes_written = 0
            with open(out_path, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    bytes_written += len(chunk)

                    # 진행 상황(실시간 느낌)
                    if "content-length" in r.headers:
                        total = int(r.headers["content-length"])
                        pct = (bytes_written / total) * 100 if total else 0
                        print(f"\rDownloading: {bytes_written}/{total} bytes ({pct:.1f}%)", end="")
                    else:
                        print(f"\rDownloading: {bytes_written} bytes", end="")

            print("\n\nSaved:", out_path)
            print("Elapsed ms:", int((time.perf_counter() - t0) * 1000))

    if args.play:
        play_wav_file(out_path)


if __name__ == "__main__":
    asyncio.run(main())
