import argparse
import asyncio
import time

import httpx
import numpy as np
import sounddevice as sd

# python tools/test_synthesize_pcm_realtime.py --voice-id CmB5LaFHgSou5vuX2SXZ

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/api/v1/ai/synthesize-response?format=pcm")
    p.add_argument("--call-id", default="call_test_001")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--text", default="안녕하세요. 실시간 PCM 스트리밍 재생 테스트입니다.")
    args = p.parse_args()

    payload = {
        "callId": args.call_id,
        "text": args.text,
        "voiceId": args.voice_id,
        "sourceType": "ai_response",
    }

    sr = 16000
    channels = 1

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", args.url, json=payload) as r:
            if r.status_code != 200:
                try:
                    print("Error JSON:", r.json())
                except Exception:
                    print("Error text:", await r.aread())
                return

            print("Streaming realtime playback... (PCM 16kHz, s16le)")
            with sd.RawOutputStream(
                samplerate=sr,
                channels=channels,
                dtype="int16",
                blocksize=0,
            ) as stream:
                async for chunk in r.aiter_bytes(chunk_size=4096):
                    if not chunk:
                        continue
                    # chunk는 s16le raw bytes라고 가정하고 바로 write
                    stream.write(chunk)

    print("Done. Elapsed ms:", int((time.perf_counter() - t0) * 1000))


if __name__ == "__main__":
    asyncio.run(main())
