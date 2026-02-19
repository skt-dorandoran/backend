# T.mate (SKT FLY AI 8기 도란도란 1팀, 통화 AI Agent)
이 프로젝트는 청각장애인을 위한 AI 음성 통화 에이전트 기능을 제공하는 Android 앱 백엔드이며, 서비스명은 T.mate입니다. Python FastAPI를 통해 주요 기능을 구현하고 서비스하여 프론트엔드를 지원합니다. 

## 주요기능
- 앱 구성
    - AI 음성 클론 모델 학습
    - AI 음성 클론 모델 삭제
- 통화
    - 실시간 음성 인식 (STT) + 침묵 감지
    - 음성 클론 모델 + 텍스트 → 음성 출력
    - AI 추천 답변 생성
    - AI 음성 교정
    - 위기 상황-이해 실패(’AI 교정’ 자동 전환)

## 시스템 구조
- STT: Deepgram Nova-3
- 음성 클로닝/TTS: Elevenlabs Eleven Multilingual V2
- 텍스트 생성: OpenAI GPT-4o
- 주요 FastAPI/Python 구조:
    - `core`: 환경 감지 및 환경변수 세팅
    - `routers`: API 라우터 관리
    - `schemas`: 입출력 구조 스키마
    - `services`: 백엔드 API 주요 기능
    - `tools`: 로컬 테스트 파일

## 빌드 및 실행 방법
1. [Python 3.11.9](https://www.python.org/downloads/release/python-3119/) 설치
2. 가상환경 구성 및 실행
    ```
    # 가상환경 구성
    python -m venv .venv

    # 가상환경 실행
    .\.venv\Scripts\activate
    ```
3. 환경변수(.env) 파일 생성 및 설정
4. 라이브러리 다운로드
    ```
    pip install -r requirements.txt
    ```
5. 로컬 서버 실행
    ```
    uvicorn main:app --reload
    ```

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
    - `ELEVENLABS_TTS_MODEL_ID`: Elevenlabs TTS 서비스 모델입니다. 기본적으로 eleven_multilingual_v2을 지정합니다.
    - `ELEVENLABS_BASE_URL`: Elevenlabs API 접속 URL입니다. 기본적으로 https://api.elevenlabs.io 를 지정합니다.
- 최종적인 .env 파일의 내용은 다음과 같습니다.
    ```
    DEEPGRAM_API_KEY=your_deepgram_api_key
    DEEPGRAM_MODEL=nova-3
    DEEPGRAM_LANGUAGE=ko
    DEEPGRAM_ENDPOINTING_MS=300
    OPENAI_API_KEY=your_open_ai_key
    ELEVENLABS_API_KEY=your_elevenlabs_ai_key
    ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
    ELEVENLABS_BASE_URL=https://api.elevenlabs.io
    ```

## 주요 버전 정보
- Python: 3.11.9

## 기술 스택
- Python, FastAPI
- Deepgram, Elevenlabs, OpenAI
- Docker, Nginx, Github Actions

## 참고 및 문서
- [AWS Lightsail 서버 세팅](https://github.com/skt-dorandoran/backend/blob/develop/service-setting/01_aws-lightsail.md)
- [Docker 세팅](https://github.com/skt-dorandoran/backend/blob/develop/service-setting/02_docker.md)
- [nginx-proxy-manager 세팅](https://github.com/skt-dorandoran/backend/blob/develop/service-setting/03_nginx-proxy-manager.md)
- [로컬 테스트](https://github.com/skt-dorandoran/backend/blob/develop/tools/README.md)