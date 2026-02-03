# docker 세팅

## 목적

docker 기반 개발/배포를 위한 로컬 및 서버 실행 환경 구축

## docker 설명

- `docker`란?
  - 애플리케이션 실행에 필요한 패키지, 코드, 도구 등을 컨테이너라는 공간에 담아 개발부터 배포, 실행까지 일관된 환경에서 안정적으로 실행될 수 있도록 돕는 플랫폼
- `docker-compose`란?
  - 여러 개의 docker 컨테이너와, 각각의 속성을 하나의 `.yml` 파일로 관리하는 것
  - 최근에는 `docker compose`로 대체되는 추세임 (`docker` 패키지 내장)

## docker 설치 (Windows) - 로컬 환경에서 수행

- Docker 공식 홈페이지에서 Docker Desktop 다운로드 및 설치
  - [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
- WSL2 설치 (Windows 10, 21H1 이상), Powershell을 관리자 권한으로 실행 후 다음 명령어 입력
  - WSL2 설치
    ```
    wsl --install
    ```
  - WSL 버전을 2로 변경(Windows 11 이상의 WSL은 자동으로 WSL2가 설치됨)
    ```
    wsl --set-default-version 2
    ```
  - WSL2 Linux 커널 업데이트 다운로드 및 설치
    - [https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi](https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi)
  - WSL 패키지 최신 업데이트
    - wsl --update
  - Microsoft Store에서 Ubuntu 패키지 설치
  - 패키지 설치 후 Ubuntu 앱 실행, 이후 `Installing. this may take few minutes...` 메세지가 사라질 때 까지 대기.
  - 이후, 리눅스 사용자 이름과 비밀번호를 지정하여 초기 셋업을 진행한다
- Windows Docker 사용 시 주의사항
  - WSL을 설치해야 Windows Docker를 사용할 수 있으며, WSL 사용 시 `제어판` - `프로그램` - `프로그램 및 기능` - `Windows 기능 켜기/끄기`에서 다음 두 가지 옵션을 켠다.
    - `Hyper-V`
    - `Linux용 Windows 하위 시스템`
  - 단, 두 가지 옵션을 켜면 `VMware` 및 `Virtual Box`는 사용할 수 없음.

## docker 설치 (Ubuntu) - 리눅스 서버에서 수행

### docker 설치
- `add-apt-repository` 명령을 사용하기 위한 패키지 설치
  ```
  sudo apt-get -y install software-properties-common
  ```
- `get-docker.sh` 안의 SSL 문제를 해결하기 위한 패키지 설치
  ```
  sudo apt-add-repository -y -r ppa:certbot/certbot
  ```
- `curl` 명령어를 이용하여 docker 패키지를 설치하는 스크립트 다운로드
  ```
  curl -fsSL get.docker.com -o ~/get-docker.sh
  ```
- docker 설치 스크립트 실행
  ```
  sh ~/get-docker.sh
  ```
- docker 설치 스크립트 제거
  ```
  rm ~/get-docker.sh
  ```
- docker 명령어 사용 시 일반 사용자 권한으로도 쓸 수 있게 설정
  - `[주의] 단, 해당 명령어 사용 후 사용하고 있던 쉘을 껐다 켜야 반영됨.`
  ```
  sudo usermod -aG docker ${USER}
  ```

### docker-compose 설치
- docker-compose 설치 스크립트를 위한 jq 라이브러리 설치
  ```
  sudo apt-get -y install jq
  ```
- 최신 버전의 docker-compose 다운로드
  ```
  sudo curl -L https://github.com/docker/compose/releases/download/$(curl --silent https://api.github.com/repos/docker/compose/releases/latest | jq .name -r)/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
  ```
- docker-compose를 실행할 수 있게 권한 변경
  ```
  sudo chmod +x /usr/local/bin/docker-compose
  ```