### 가상 전화망 구성

- 기술스택
    - TURN(coturn)
    - WebRTC 시그널링(Node.js)

- 포트 사용
    - TURN
        - TCP/UDP: 3478
        - TLS(TCP): 5349
        - 릴레이 포트(UDP): 49160-49200
    - WebRTC
        - TCP: 8080

- turnserver.conf
    - 필수 수정 값
        - realm
        - external-ip
        - 계정(또는 secret)
        - 인증서(선택)

- signaling/server.js
    - 방 join
    - offer/answer/ice 릴레이

- 방화벽 필수 오픈 포트
    - 3478/udp, 3478/tcp (TURN)
    - 5349/tcp (TURN over TLS, 선택)
    - 49160-49200/udp (릴레이 포트 대역)
    - 8080/tcp (시그널링)
    - ufw 사용 시
        ```
        sudo ufw allow 8080/tcp
        sudo ufw allow 3478/udp
        sudo ufw allow 3478/tcp
        sudo ufw allow 5349/tcp
        sudo ufw allow 49160:49200/udp
        ```

- 서비스 실행
    - (최초 한 번)
        ```
        mkdir -p turn/data turn/log signaling
        ```
    ```
    docker compose up -d --build
    ```
    ```
    docker logs -f coturn
    ```
    ```
    docker logs -f webrtc_signaling
    ```

- 클라이언트 설정 예시
    - STUN: stun:YOUR_DOMAIN_OR_IP:3478 (가능하면 별도 STUN도 OK)
    - TURN: turn:YOUR_DOMAIN_OR_IP:3478?transport=udp
    - TURN(TCP): turn:YOUR_DOMAIN_OR_IP:3478?transport=tcp
    - username/password: webrtc / STRONG_PASSWORD_HERE

- webrtc-test.html
    - const SIGNALING_URL = "ws://YOUR_SERVER_IP:8080";
    - stun:YOUR_SERVER_IP:3478
    - turn:YOUR_SERVER_IP:3478
    - username: "webrtc"
    - credential: "STRONG_PASSWORD_HERE"
    - turn 설정과 turnserver.conf의 계정이 반드시 일치해야 함

- 테스트 방법
    - Chrome 브라우저 2개 탭 열기
    - 같은 room id 입력 (test-room)
    - 두 탭 모두 Join 클릭
    - 한쪽 탭에서만 Call 클릭
    - 서로 음성이 들리면 성공

- Nginx Proxy Manager 설정
    - 도메인 추가
    - WebSocket 설정 추가
    - 추가 설정
        ```
        location / {
            proxy_pass http://webrtc_signaling:8080;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
        ```
    - 프론트엔드 수정
        ```
        const SIGNALING_URL = "ws://YOUR_SERVER_IP:8080";
        ```
        ```
        const SIGNALING_URL = "wss://YOUR_SERVER_DOMAIN";
        ```