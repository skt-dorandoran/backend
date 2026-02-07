# 로컬 테스트

## 유의사항
- 모든 명령어 기반 실행은 최상위 폴더에서 수행합니다.
- 로컬 환경변수(.env)는 최상위 폴더에 위치하면 됩니다.
- 환경변수로는 다음과 같은 내용이 포함되어야 합니다.
    ```
    DEEPGRAM_API_KEY=your_deepgram_api_key
    DEEPGRAM_MODEL=nova-3
    DEEPGRAM_LANGUAGE=ko
    DEEPGRAM_ENDPOINTING_MS=300
    OPENAI_API_KEY=your_open_ai_key
    ELEVENLABS_API_KEY=your_elevenlabs_ai_key
    ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
    ```

## STT 테스트
### test_deepgram_local_latency.py
테스트 1단계, 로컬 파일을 입력받아 속도를 측정합니다.

- 기본 실행
    ```
    python tools/test_deepgram_local_latency.py --wav tools/wav_test.wav
    ```

- 파라미터 포함 실행
    ```
    python tools/test_deepgram_local_latency.py \
    --wav tools/wav_test.wav \              // 테스트 음성 파일명(항상 wav)
    --model nova-3 \                        // Deepgram 모델 (기본 nova-3)
    --language ko \                         // 인식 언어 (기본 한국어)
    --chunk-ms 50 \                         // 청크 입력 속도 (기본 75)
    --realtime \                            // 실시간성 플래그
    --endpointing 250 \                     // 발화가 끝났다고 판단하는 시간
    --no-interim \                          // 중간 과정 출력 플래그
    --no-punctuate \                        // 문장부호 자동 보정 플래그
    --no-smart-format \                     // 자연스러운 포맷팅 플래그 
    --final-wait-sec 3 \                    // 마지막 final 결과가 도착할 시간을 추가로 기다리는 시간
    --verbose \                             // 켜면 수신되는 텍스트를 즉시 출력 플래그
    ```

### test_mic_realtime.py
테스트 2단계, 로컬에서 사용자가 마이크로 음성을 입력하여 출력을 확인합니다.
```
python -m tools.test_mic_realtime
```

### index.html
테스트 3단계, 간이적인 프론트엔드-웹소켓 연결로 로컬에서 사용자가 마이크로 음성을 입력하여 출력을 확인합니다.

로컬 프론트엔드의 실행을 위해 main.py에서 기존의 @app.get("/") 부분을 주석 처리하고 
```
@app.get("/")
def main():
    return "Goodbye Everyone, Hello SKT FLY AI!"
```

파일 하단 아래 @app.get("/") 부분의 주석을 해제한 뒤 로컬에서 접속하면 됩니다.
```
from fastapi.responses import FileResponse

@app.get("/")
async def get_test_page():
    return FileResponse("tools/index.html")
```

## TTS 테스트
아래 테스트는 클론된 Elevenlabs 음성 모델 ID를 요구합니다.

### test_synthesize_wav.py
테스트 1단계, 모델 ID와 문장을 입력받아 wav 파일을 생성합니다.
- 기본 실행
    ```
    python tools/test_synthesize_wav.py --voice-id YOUR_VOICE_ID --play
    ```
- 파라미터 포함 실행
    ```
    python tools/test_synthesize_wav.py \
    --call-id "call_test_001" \             // 음성 세션의 ID 부여
    --voice-id YOUR_VOICE_ID \              // 클론된 음성의 Elevenlabs 호출 ID
    --text "example" \                      // 출력할 텍스트 문장
    --source-type "ai_response" \           // 출력 유형, "ai_response", "corrected", "typed" 중 하나 선택
    --out "response_audio.wav" \            // 출력 저장 파일 명칭 및 형식
    --play                                  // 다운로드 완료 후 자동 재생
    ```

### test_synthesize_pcm_realtime.py
테스트 2단계, 모델 ID와 문장을 입력받아 실시간에 가깝게 출력합니다.
- 기본 실행
    ```
    python tools/test_synthesize_pcm_realtime.py --voice-id YOUR_VOICE_ID
    ```
- 파라미터 포함 실행
    ```
    python tools/test_synthesize_pcm_realtime.py \
    --call-id "call_test_001" \             // 음성 세션의 ID 부여
    --voice-id YOUR_VOICE_ID \              // 클론된 음성의 Elevenlabs 호출 ID
    --text "example" \                      // 출력할 텍스트 문장
    ```