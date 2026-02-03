# nginx-proxy-manager 세팅

## 목적

Docker Compose 기반 Nginx Proxy Manager를 이용한 리버스 프록시 및 HTTPS 운영 환경 구축

## docker-compose를 이용한 npm 설치
- mariadb를 이용하여 npm이 사용할 데이터베이스 구성
- mariadb가 실행된 후, npm이 실행될 수 있도록 `depends_on` 설정
  - 파일 생성 후 `docker-compose-static.yml` 이름으로 해당 내용 저장
  ```
  services:
    npm:
      image: 'jc21/nginx-proxy-manager:latest'
      container_name: npm
      ports:
        - '80:80'
        - '443:443'
        - '8088:81'
      environment:
        TZ: Asia/Seoul
        DB_MYSQL_HOST: "npmdb"
        DB_MYSQL_PORT: 3306
        DB_MYSQL_USER: "npmuser"
        DB_MYSQL_PASSWORD: "dorandoran"
        DB_MYSQL_NAME: "npm"
      volumes:
        - ./npm/data:/data
        - /etc/letsencrypt:/etc/letsencrypt
      restart: unless-stopped
      depends_on:
        - npmdb
    
    npmdb:
      image: mariadb
      container_name: npmdb
      environment:
        MYSQL_ROOT_PASSWORD: 'dorandoran'
        MYSQL_DATABASE: 'npm'
        MYSQL_USER: 'npmuser'
        MYSQL_PASSWORD: 'dorandoran'
        TZ: Asia/Seoul
      volumes:
        - ./npmdb/data/mysql:/var/lib/mysql
      restart: unless-stopped

  networks:
    default:
      name: dorandoran
  ```
- `docker-compose-static.yml` 실행
  - 백그라운드로 실행해야 하기 때문에, 반드시 데몬 옵션(`-d`)을 붙여 실행
  ```
  docker-compose -f docker-compose-static.yml up -d
  ```
- AWS Lightsail의 웹 콘솔에서 8088포트에 대한 아웃바운드 권한 개방(또는 관리자에게 요청)
  - 네트워킹 탭의 IPv4 방화벽, TCP/8088포트 규칙 생성

## nginx-proxy-manager 계정 설정
- Chrome 브라우저를 이용하여 `http://dorandoran.duckdns.org:8088/` 페이지로 이동(반드시 `http`여야 함)
- 새로운 관리자 계정 생성
  - Full Name: 관리자 이름 (영어로 충분)
  - Email address: 사용할 아이디 (이메일 형식)
  - New Password: 사용할 비밀번호
  - 이후 로그인 부터는 `Email address`와 `Password`를 이용하여 계정 접속

## 와일드카드 도메인에 대한 SSL 인증서 생성
- `Certificates` 버튼 클릭
- `Add Certificate` 버튼 클릭
- `Let's Encrypt via DNS` 버튼 클릭
- Domain Names에 다음 도메인 입력
  - `*.dorandoran.duckdns.org`
  - `dorandoran.duckdns.org`
- DNS Provider에서 `DuckDNS` 선택
- `Credentials File Content` 에서 다음 내용 편집
  - 기존 내용 중 `your-duckdns-token`를 지우고, `=` 다음에 해당 내용 입력
    - `duckdns.org`에 접속 후, `token` 옆에 있는 36자리의 토큰을 복사하여 사용
    - 토큰은 DNS 호스팅 사이트에서 발급
- `Save` 버튼 클릭. 로딩 대기. (SSL 인증서 발급)
  - `Internal Error` 발생 시, SSL 인증서 발급이 실패한 것이므로 재시도
- 정상적인 SSL 발급이 된다면, `Success. Certificate has been saved` 라는 문구가 우측 상단에 잠시동안 메시지가 뜨고 사라짐
- 이후부터, npm(nginx proxy manager)이 SSL 인증서를 자동으로 갱신

## Nginx Proxy Manager에 SSL 인증서 부여
- `Hosts` - `Proxy Hosts` 버튼 클릭
- `Add Proxy Host` 버튼 클릭
- 다음 정보 입력
  - Domain Names에 `npm.dorandoran.duckdns.org` 입력
  - Forward Hostname / IP에 `npm` 입력 (npm의 컨테이너 이름)
    - docker는 아이피 혹은 컨테이너 이름으로 통신할 수 있다
  - Forward Port에 `81` 입력 (컨테이너의 내부 통신 포트)
  - Websockets Support의 버튼을 `활성화`
  - SSL 탭에 들어가, SSL Certificate을 None 대신 `*dorandoran.duckdns.org, dorandoran.duckdns.org`로 설정.
  - 이후, `Save` 버튼 클릭
  - AWS Lightsail의 웹 콘솔에서 443포트에 대한 아웃바운드 권한 개방(또는 관리자에게 요청)
    - 네트워킹 탭의 IPv4 방화벽, TCP/443포트 규칙 생성 (HTTPS)
  - 해당 세팅 이후부터, npm에 접속하기 위해 `https://npm.dorandoran.duckdns.org` 주소로 접속

## drdr-backend에 SSL 인증서 부여
- `Hosts` - `Proxy Hosts` 버튼 클릭
- `Add Proxy Host` 버튼 클릭
- 다음 정보 입력
  - Domain Names에 `dorandoran.duckdns.org` 입력
  - Forward Hostname / IP에 `drdr-backend` 입력 (drdsr-backend의 컨테이너 이름)
    - docker는 아이피 혹은 컨테이너 이름으로 통신할 수 있다
  - Forward Port에 `8000` 입력 (컨테이너의 내부 통신 포트)
  - Websockets Support의 버튼을 `활성화`
  - SSL 탭에 들어가, SSL Certificate을 None 대신 `*dorandoran.duckdns.org, dorandoran.duckdns.org`로 설정.
  - 이후, `Save` 버튼 클릭
  - 해당 세팅 이후부터, drdr-backend에 접속하기 위해 `https://dorandoran.duckdns.org` 주소로 접속(반드시 `https`여야 함)
  - 해당 세팅 이후부터, 기존의 8088포트는 닫아도 됨