import asyncio
import sys
import pyaudio
import os
from pathlib import Path
from dotenv import load_dotenv

from clients.deepgram_client import DeepgramStreamingClient
from core.settings import settings

# .env 로드
load_dotenv()

# 오디오 설정 (Deepgram 권장 기본값)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000  # 0.5초 단위 프레임

def extract_transcript_safe(dg_msg):
    """
    Deepgram 응답 메시지에서 안전하게 transcript를 추출하는 함수.
    리스트와 딕셔너리 구조를 모두 대응합니다.
    """
    # 1. 메시지 자체가 리스트인 경우 처리
    if isinstance(dg_msg, list):
        if len(dg_msg) > 0:
            dg_msg = dg_msg[0]
        else:
            return "", False

    if not isinstance(dg_msg, dict):
        return "", False

    # 2. 'channel' 키 접근
    channel = dg_msg.get("channel")
    
    # channel이 리스트인 경우 ([{ "alternatives": [...] }]) 처리
    if isinstance(channel, list):
        if len(channel) > 0:
            channel = channel[0]
        else:
            channel = {}
    
    if not isinstance(channel, dict):
        return "", False

    # 3. 'alternatives' 키 접근
    alts = channel.get("alternatives")
    if not isinstance(alts, list) or not alts:
        return "", False

    # 4. 데이터 추출
    a0 = alts[0]
    transcript = a0.get("transcript", "")
    is_final = dg_msg.get("is_final", False)
    
    return transcript, is_final

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
    
    try:
        while not stop_event.is_set():
            # 마이크 데이터를 비차단 방식으로 읽기
            data = await asyncio.to_thread(stream.read, CHUNK, exception_on_overflow=False)
            yield data
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

async def run_mic_test():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("에러: DEEPGRAM_API_KEY가 설정되지 않았습니다.")
        return

    stop_event = asyncio.Event()

    async with DeepgramStreamingClient(
        api_key=api_key,
        model="nova-3",          # 최신 모델 사용
        language="ko",           # 한국어 설정
        encoding="linear16",
        sample_rate=RATE,
        channels=CHANNELS,
        interim_results=True,
        endpointing_ms=300       # 앞서 테스트한 최적값 적용
    ) as dg:

        # 1. 수신 루프 (Deepgram 결과 받기)
        async def recv_loop():
            try:
                async for msg in dg.recv_events():
                    transcript, is_final = extract_transcript_safe(msg)
                    if transcript:
                        if is_final:
                            print(f"\n✅ [최종 확인]: {transcript}")
                        else:
                            # 중간 결과는 한 줄에서 갱신되도록 출력
                            sys.stdout.write(f"\r⏳ [인식 중]: {transcript}")
                            sys.stdout.flush()
            except Exception as e:
                print(f"\n[수신 에러] {e}")

        # 2. 송신 루프 (마이크 데이터를 Deepgram으로 보내기)
        async def send_loop():
            try:
                async for chunk in mic_stream_generator(stop_event):
                    await dg.send_audio(chunk)
            except Exception as e:
                print(f"\n[송신 에러] {e}")

        # 수신과 송신을 동시에 실행
        await asyncio.gather(recv_loop(), send_loop())

if __name__ == "__main__":
    try:
        asyncio.run(run_mic_test())
    except KeyboardInterrupt:
        print("\n\n종료합니다.")
