import { WebSocketServer } from "ws";

const wss = new WebSocketServer({ port: 8080 });

const rooms = new Map(); // roomId -> Set<ws>

function safeSend(ws, obj) {
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(obj));
}

wss.on("connection", (ws) => {
  ws.roomId = null;

  ws.on("message", (data) => {
    let msg;
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }

    const { type, roomId } = msg;

    if (type === "join") {
      if (ws.roomId) {
        const prev = rooms.get(ws.roomId);
        if (prev) prev.delete(ws);
      }
      ws.roomId = roomId;
      if (!rooms.has(roomId)) rooms.set(roomId, new Set());
      rooms.get(roomId).add(ws);

      // 현재 인원 수 알려주기 (옵션)
      safeSend(ws, { type: "joined", roomId, peers: rooms.get(roomId).size - 1 });
      return;
    }

    // offer/answer/ice는 같은 room의 다른 클라이언트에게 브로드캐스트
    if (!ws.roomId) return;
    const peers = rooms.get(ws.roomId);
    if (!peers) return;

    for (const peer of peers) {
      if (peer !== ws) safeSend(peer, msg);
    }
  });

  ws.on("close", () => {
    if (!ws.roomId) return;
    const peers = rooms.get(ws.roomId);
    if (!peers) return;
    peers.delete(ws);
    if (peers.size === 0) rooms.delete(ws.roomId);
  });
});

console.log("Signaling server listening on :8080");
