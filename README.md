# backend
Backend for dorandoran project

## 환경변수
- 로컬 환경변수(.env)는 최상위 폴더에 위치하면 됩니다.
- 모든 로컬 명령어 기반 테스트 코드 실행은 최상위 폴더에서 수행합니다.
- 환경변수로는 다음과 같은 내용이 포함되어야 합니다.
    - `DEEPGRAM_API_KEY`: Deepgram 서비스 API 키입니다. **비밀 키이므로 유출되어서는 안됩니다.**
    - `DEEPGRAM_MODEL`: Deepgram STT 서비스 모델입니다. 기본적으로 Nova-3을 지정합니다.
    - `DEEPGRAM_LANGUAGE`: Deepgram STT 서비스 언어입니다. 기본적으로 ko(한국어)을 지정합니다.
    - `DEEPGRAM_ENDPOINTING_MS`: Deepgram STT 서비스 엔드포인트(문장 별 일시정지) 시간입니다. 기본적으로 300ms을 지정합니다.
    - `OPENAI_API_KEY`: OpenAI 서비스 API 키입니다. **비밀 키이므로 유출되어서는 안됩니다.**
    - `ELEVENLABS_API_KEY`: Elevenlabs 서비스 API 키입니다. **비밀 키이므로 유출되어서는 안됩니다.**
- 최종적인 .env 파일의 내용은 다음과 같습니다.
    ```
    DEEPGRAM_API_KEY=your_deepgram_api_key
    DEEPGRAM_MODEL=nova-3
    DEEPGRAM_LANGUAGE=ko
    DEEPGRAM_ENDPOINTING_MS=300
    OPENAI_API_KEY=your_open_ai_key
    ELEVENLABS_API_KEY=your_open_ai_key
    ```

## 기능