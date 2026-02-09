"""
WebSocket STT API + 침묵 감지 기능 테스트

사용법:
1. 서버 실행: python -m uvicorn main:app --reload
2. 이 스크립트 실행: python tools/test_ws_silence_detection.py

침묵 감지 테스트:
- 8초간 말하지 않으면 "silence_detected" 이벤트가 발생합니다.
- 다시 말하면 타이머가 리셋됩니다.
"""

import asyncio
import sys
import json
import pyaudio
import websockets
from datetime import datetime


# 오디오 설정
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000  # 0.5초 단위

# WebSocket 설정
WS_URL = "ws://127.0.0.1:8000/api/v1/speech/transcribe/ws"

# 침묵 감지 설정 (None이면 비활성화)
SILENCE_THRESHOLD = 8.0  # 8초간 침묵 시 알림


async def mic_stream_generator(stop_event):
    """마이크에서 음성을 읽어오는 비동기 제너레이터"""
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print("\n🎤 마이크 입력을 시작합니다... (종료하려면 Ctrl+C)")
    print(f"⏱️  침묵 감지 설정: {SILENCE_THRESHOLD}초\n")

    try:
        while not stop_event.is_set():
            data = await asyncio.to_thread(stream.read, CHUNK, exception_on_overflow=False)
            yield data
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


async def run_ws_test():
    """WebSocket 서버에 연결하여 STT + 침묵 감지 테스트"""
    stop_event = asyncio.Event()

    try:
        async with websockets.connect(WS_URL) as ws:
            print(f"✅ WebSocket 연결 성공: {WS_URL}\n")

            # 1. 초기화 메시지 전송 (sampleRate + silenceThreshold)
            init_msg = {"sampleRate": RATE}
            if SILENCE_THRESHOLD is not None:
                init_msg["silenceThreshold"] = SILENCE_THRESHOLD

            await ws.send(json.dumps(init_msg))
            print(f"📤 초기화 메시지 전송: {init_msg}\n")

            # 2. 수신 루프 (서버로부터 결과 받기)
            async def recv_loop():
                try:
                    async for message in ws:
                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "final":
                            print(f"\n✅ [최종]: {data.get('text')}")
                            print(f"   신뢰도: {data.get('confidence'):.2f}")

                        elif msg_type == "interim":
                            sys.stdout.write(f"\r⏳ [인식 중]: {data.get('text')}")
                            sys.stdout.flush()

                        elif msg_type == "silence_detected":
                            duration = data.get("silenceDuration")
                            timestamp = data.get("timestamp")
                            print(f"\n\n🔇 [침묵 감지!]")
                            print(f"   지속 시간: {duration}초")
                            print(f"   감지 시각: {timestamp}")
                            print(f"   → 다시 말하면 타이머가 리셋됩니다.\n")

                        elif msg_type == "error":
                            print(f"\n❌ 에러: {data.get('text')}")
                            stop_event.set()

                except Exception as e:
                    print(f"\n[수신 에러] {e}")
                finally:
                    stop_event.set()

            # 3. 송신 루프 (마이크 데이터를 서버로 보내기)
            async def send_loop():
                try:
                    async for chunk in mic_stream_generator(stop_event):
                        if stop_event.is_set():
                            break
                        await ws.send(chunk)
                except Exception as e:
                    print(f"\n[송신 에러] {e}")
                finally:
                    stop_event.set()

            # 수신과 송신을 동시에 실행
            await asyncio.gather(recv_loop(), send_loop())

    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket 연결 실패: {e}")
        print(f"\n💡 서버가 실행 중인지 확인하세요:")
        print(f"   python -m uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ 에러: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket STT + 침묵 감지 테스트")
    print("=" * 60)
    print(f"\n서버 URL: {WS_URL}")
    print(f"샘플레이트: {RATE} Hz")
    print(f"침묵 감지 임계값: {SILENCE_THRESHOLD}초 (None이면 비활성화)")
    print("\n침묵 감지 테스트 방법:")
    print("  1. 말하기 시작")
    print("  2. 8초간 침묵 유지")
    print("  3. 'silence_detected' 이벤트 확인")
    print("  4. 다시 말하면 타이머 리셋 확인")
    print("\n침묵 감지 비활성화 테스트:")
    print("  - SILENCE_THRESHOLD = None으로 설정 후 실행")
    print("  - 아무리 침묵해도 이벤트가 발생하지 않아야 함")
    print("=" * 60)

    try:
        asyncio.run(run_ws_test())
    except KeyboardInterrupt:
        print("\n\n종료합니다.")
