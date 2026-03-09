# Frontend 변경 안내 (WebRTC 시그널링)

다음은 서버(`server.js`)에서의 변경(hangup 브로드캐스트, 개선된 종료 처리)에 맞춰 프론트엔드에서 반드시 지켜야 할 사항입니다.

## 1) 항상 `callId` 포함
- `offer`, `answer`, `ice` 메시지는 반드시 `callId` 필드를 포함해야 합니다.
- 예:
  ```json
  { "type": "offer", "callId": "<callId>", "offer": { ... } }
  ```
- 서버는 `callId`를 기준으로 해당 통화의 호출자/수신자에게만 릴레이합니다. `callId`가 없으면 릴레이되지 않습니다.

## 2) 호출 흐름 요약 (클라이언트 구현 지침)
- 수신자 앱 실행 시: `subscribe` (roomId 포함)
  ```js
  ws.send(JSON.stringify({ type: 'subscribe', roomId }));
  ```
- 호출자 통화 시도: `call` (roomId 포함). 서버가 `callId` 생성 후 구독자들에게 `incoming` 전송.
  ```js
  ws.send(JSON.stringify({ type: 'call', roomId }));
  // 응답: incoming { callId }
  ```
- 수신자 수락: `accept` (roomId, callId 포함)
  ```js
  ws.send(JSON.stringify({ type: 'accept', roomId, callId }));
  // 서버가 호출자에게 `callee_joined` 전송
  ```
- 호출자: `callee_joined` 수신 시 `offer` 생성하여 `callId` 포함해 전송
  ```js
  ws.send(JSON.stringify({ type: 'offer', callId, offer }));
  ```
- 수신자: `offer` 수신 후 `answer` 생성하여 `callId` 포함해 전송

## 3) 끊기/비정상 종료 처리
- 사용자가 직접 끊을 때 앱은 `hangup` 메시지를 서버로 먼저 전송한 뒤 WebSocket을 닫으세요.
  ```js
  ws.send(JSON.stringify({ type: 'hangup', roomId, callId }));
  ws.close();
  ```
- 네트워크로 인해 소켓이 끊길 경우(클라이언트가 `hangup`을 보내지 못한 경우) 서버가 연결 종료를 감지하고 다음 메시지를 전송합니다:
  - 수신자/구독자: `{ type: 'hangup', roomId, callId }` 혹은 `{ type: 'peer_left', roomId }`
- 클라이언트는 `hangup` 또는 `peer_left` 메시지를 받으면 통화 UI를 종료하고 로컬 PeerConnection을 닫으세요.

## 4) Offer/Answer/ICE 버퍼링 고려
- 서버는 `callId`가 생성된 뒤라도 수신자가 아직 연결되지 않았을 때 `offer`/`ice`를 버퍼링하도록 지원합니다.
- 그러나 클라이언트는 `callee_joined` 이벤트를 받고 난 뒤 offer 전송 플로우를 확실히 따르도록 구현하는 것이 가장 안전합니다.

## 5) 로깅 및 디버그
- 통화 문제가 발생하면 브라우저/앱 콘솔에 다음 로그를 남기세요:
  - WS 수신/송신 메시지 타입과 `callId`, `roomId`
  - PeerConnection 상태 이벤트(`iceconnectionstatechange`, `connectionstatechange`)
- 서버의 `RECV:` / `SENT:` 로그를 함께 제출하면 빠른 원인 분석에 도움이 됩니다.

## 6) 요약된 변경 포인트 (서버와의 계약)
- `callId`는 필수 필드입니다.
- 사용자가 먼저 끊는 경우 `hangup`을 서버로 전송하세요.
- 클라이언트가 비정상적으로 연결이 끊기면 서버가 `hangup` 또는 `peer_left`를 브로드캐스트하므로 이를 처리하세요.

---

궁금한 점이 있거나, 프론트엔드 예제 코드를 원하시면 어떤 플랫폼(웹/안드로이드/iOS)인지 알려주세요. 제가 예제 코드를 만들어 드리겠습니다.