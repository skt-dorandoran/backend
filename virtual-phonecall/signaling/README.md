# WebRTC 시그널링 서버 업데이트 내역

## 개요
호출자/수신자 구분 통화 플로우를 지원하도록 `server.js`를 수정했습니다. 기존 단순 room broadcast 방식에서 **1:1 호출 및 릴레이** 기능으로 진화했습니다.

---

## 주요 변경사항

### 1. 새로운 데이터 구조 추가
```javascript
const subscribers = new Map();  // roomId -> Set<ws> (수신 대기 중인 사용자)
const calls = new Map();        // callId -> { caller, callee, roomId, status }
```
- **subscribers**: 특정 room에서 통화를 대기하는 클라이언트들 추적
- **calls**: 각 통화 상태 관리 (호출자, 수신자, room ID, 상태)

### 2. 클라이언트 → 서버 메시지 핸들러 추가

#### `subscribe` (수신 대기)
```javascript
if (type === "subscribe") {
  if (!roomId) return;
  addToSetMap(subscribers, roomId, ws);
  ws.subscribedRooms.add(roomId);
  safeSend(ws, { type: "subscribed", roomId });
  return;
}
```
- 앱 실행 시 수신 대기 시작
- room의 구독자 목록에 클라이언트 추가

#### `call` (통화 시도)
```javascript
if (type === "call") {
  if (!roomId) return;
  const id = randomUUID();
  calls.set(id, { caller: ws, callee: null, roomId, status: "ringing" });
  ws.currentCallId = id;

  const subs = subscribers.get(roomId);
  if (subs) {
    for (const sub of subs) {
      safeSend(sub, { type: "incoming", roomId, callId: id });
    }
  }
  return;
}
```
- 고유한 `callId` 생성
- 호출자 정보 저장
- 같은 room의 모든 구독자에게 `incoming` 알림 발송

#### `accept` (통화 수락)
```javascript
if (type === "accept") {
  if (!callId) return;
  const call = calls.get(callId);
  if (!call) return;
  if (call.roomId && !ws.subscribedRooms.has(call.roomId)) return;
  call.callee = ws;
  call.status = "active";
  ws.currentCallId = callId;
  safeSend(call.caller, { type: "callee_joined", callId });
  return;
}
```
- 수신자가 호출을 수락
- 호출자에게 `callee_joined` 전송
- 이후 offer/answer/ice는 호출자↔수신자만 릴레이

#### `reject` (통화 거절)
```javascript
if (type === "reject") {
  if (!callId) return;
  const call = calls.get(callId);
  if (!call) return;
  call.status = "rejected";
  safeSend(call.caller, { type: "rejected", callId });
  if (call.caller) call.caller.currentCallId = null;
  if (call.callee) call.callee.currentCallId = null;
  calls.delete(callId);
  return;
}
```
- 호출자에게 `rejected` 알림
- call 상태 정리 및 삭제

### 3. WebRTC 메시지 1:1 릴레이
```javascript
if (callId && (type === "offer" || type === "answer" || type === "ice")) {
  const call = calls.get(callId);
  if (!call) return;
  // from caller -> to callee
  if (call.caller === ws && call.callee) {
    safeSend(call.callee, msg);
    return;
  }
  // from callee -> to caller
  if (call.callee === ws && call.caller) {
    safeSend(call.caller, msg);
    return;
  }
  return;
}
```
- offer/answer/ice는 **해당 호출의 호출자와 수신자에게만** 릴레이
- 다른 클라이언트에겐 전달 안 함 (privacy, 성능)

### 4. 연결 종료 시 cleanup
```javascript
ws.on("close", () => {
  // remove from legacy rooms
  if (ws.roomId) removeFromSetMap(rooms, ws.roomId, ws);
  // remove from subscribers
  for (const r of ws.subscribedRooms) removeFromSetMap(subscribers, r, ws);

  // cleanup any active or ringing call this socket participated in
  const cid = ws.currentCallId;
  if (cid) {
    const call = calls.get(cid);
    if (call) {
      const other = call.caller === ws ? call.callee : call.caller;
      if (other) safeSend(other, { type: "rejected", callId: cid });
      calls.delete(cid);
    }
    ws.currentCallId = null;
  }
});
```
- 클라이언트 연결 종료 시 모든 room/subscriber 제거
- 진행 중인 호출이 있으면 상대방에게 거절 알림 전송

---

## 통화 흐름 (예시)

### 시나리오: A가 B에게 전화 걸기

#### 1단계: B가 앱을 켜서 대기 (B)
```json
{
  "type": "subscribe",
  "roomId": "dorandoran-room"
}
```
→ 서버: B를 구독자 목록에 추가

#### 2단계: A가 전화 건다 (A)
```json
{
  "type": "call",
  "roomId": "dorandoran-room"
}
```
→ 서버: 
- callId 생성 (예: `123e4567-e89b-12d3-a456-426614174000`)
- A를 호출자로 저장
- B에게 incoming 발송:
```json
{
  "type": "incoming",
  "roomId": "dorandoran-room",
  "callId": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### 3단계: B가 수락 (B)
```json
{
  "type": "accept",
  "roomId": "dorandoran-room",
  "callId": "123e4567-e89b-12d3-a456-426614174000"
}
```
→ 서버: A에게 callee_joined 발송:
```json
{
  "type": "callee_joined",
  "callId": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### 4단계: A가 offer 전송 (A)
```json
{
  "type": "offer",
  "callId": "123e4567-e89b-12d3-a456-426614174000",
  "offer": { ... SDP ... }
}
```
→ 서버: B에게만 릴레이 (다른 구독자 아님)

#### 5단계: B가 answer 전송 (B)
```json
{
  "type": "answer",
  "callId": "123e4567-e89b-12d3-a456-426614174000",
  "answer": { ... SDP ... }
}
```
→ 서버: A에게만 릴레이

#### 6단계: ICE candidate 교환
- A → 서버 → B
- B → 서버 → A

#### 7단계: 전화 종료
- A 또는 B가 WebSocket 종료
- 서버: 상대방에게 `{ type: "rejected", callId: ... }` 전송
- call 상태 정리

---

## 보조 유틸 함수

### `addToSetMap(map, key, value)`
- Map<key, Set<value>>에 아이템 추가
- key가 없으면 자동 생성

### `removeFromSetMap(map, key, value)`
- Set에서 value 제거
- Set이 비면 key 자체도 삭제 (메모리 효율)

---

## 기존 기능 (유지됨)

### `join` (레거시)
- 단순 room broadcast (호환성 유지)
- offer/answer/ice는 여전히 같은 room 모든 사용자에게 브로드캐스트

---

## Docker 배포

### Dockerfile
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 8080
CMD ["npm","run","start"]
```

### package.json
```json
{
  "name": "webrtc-signaling",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "ws": "^8.18.0"
  }
}
```

### 로컬 테스트
```bash
npm install
node server.js
# 포트 8080에서 리스닝
```

### Docker 실행
```bash
docker-compose up -d signaling
docker logs -f webrtc_signaling
```

---

## nginx-proxy-manager 설정

### WSS 프록시 설정
```nginx
location / {
  proxy_pass http://webrtc_signaling:8080;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header Host $host;
}
```

- **도메인**: `wss.dorandoran.duckdns.org`
- **업스트림**: `http://webrtc_signaling:8080` (Docker 내부 호스트명)
- **WebSocket 헤더**: Upgrade, Connection 필수

---

## 문제 해결

### 502 Bad Gateway
- **원인**: nginx-proxy-manager가 upstream DNS를 캐시하다가 컨테이너 IP 변경 후 갱신 안 됨
- **해결**: `docker restart npm` → nginx 재로드 및 DNS 캐시 초기화

### WebSocket 연결 실패
1. 서버가 8080에서 리스닝 중인지 확인
   ```bash
   docker logs webrtc_signaling
   ```
2. npm 컨테이너에서 upstream 접근 가능한지 확인
   ```bash
   docker exec npm getent hosts webrtc_signaling
   docker exec npm curl -sv http://webrtc_signaling:8080/
   ```
3. npm nginx 에러 로그 확인
   ```bash
   docker exec npm tail -f /data/logs/proxy-host-4_error.log
   ```

---

## 성능 고려사항

- **메모리**: calls, subscribers Maps는 연결당 최소 메모리 사용
- **연결당 비용**: 활성 call마다 2개 WebSocket 참조 + 메타데이터
- **메시지 필터링**: 1:1 릴레이로 불필요한 브로드캐스트 제거 → 트래픽 감소

---

## 향후 확장 사항 (옵션)

- 통화 기록 저장 (database 연동)
- 재통화/콜백 기능
- 미스드 콜 알림
- 부재 중 전화 메시지 (voicemail)
- 다중 피어 지원 (conference 모드)
