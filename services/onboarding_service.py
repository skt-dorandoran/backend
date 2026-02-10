import uuid, json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Tuple, List
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import UploadFile, HTTPException
from core.settings import settings

def _now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()

# ---- 1) 편집거리 기반 alignment (MVP) ----
def align_edit_ops(a: str, b: str) -> List[Tuple[str, str]]:
    """
    a=expected, b=recognized
    return ops list of (from_char, to_char)
    deletion: (x, "")
    insertion: ("", y)
    substitution: (x, y) where x!=y
    match: (x, x)
    """
    # DP
    n, m = len(a), len(b)
    dp = [[0]*(m+1) for _ in range(n+1)]
    bt = [[None]*(m+1) for _ in range(n+1)]
    for i in range(1, n+1):
        dp[i][0] = i; bt[i][0] = ("del", i-1, 0)
    for j in range(1, m+1):
        dp[0][j] = j; bt[0][j] = ("ins", 0, j-1)
    for i in range(1, n+1):
        for j in range(1, m+1):
            cost = 0 if a[i-1] == b[j-1] else 1
            cand = [
                (dp[i-1][j] + 1, ("del", i-1, j)),
                (dp[i][j-1] + 1, ("ins", i, j-1)),
                (dp[i-1][j-1] + cost, ("sub" if cost else "match", i-1, j-1))
            ]
            dp[i][j], bt[i][j] = min(cand, key=lambda x: x[0])

    # backtrack
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        t = bt[i][j]
        if t is None:
            break
        kind, pi, pj = t
        if kind == "del":
            ops.append((a[pi], ""))
            i -= 1
        elif kind == "ins":
            ops.append(("", b[pj]))
            j -= 1
        else:
            ops.append((a[pi], b[pj]))
            i -= 1; j -= 1
    ops.reverse()
    return ops

def compute_error_pattern(expected: str, recognized: str) -> Dict[str, Any]:
    ops = align_edit_ops(expected, recognized)
    subs, dels, ins = {}, {}, {}

    for fr, to in ops:
        if fr == to:
            continue
        if fr == "" and to != "":
            ins[to] = ins.get(to, 0) + 1
        elif fr != "" and to == "":
            dels[fr] = dels.get(fr, 0) + 1
        else:
            key = f"{fr}->{to}"
            subs[key] = subs.get(key, 0) + 1

    topk = sorted(
        [{"from": k.split("->")[0], "to": k.split("->")[1], "count": v} for k, v in subs.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:20]

    return {
        "substitutions": subs,
        "deletions": dels,
        "insertions": ins,
        "confusionTopK": topk,
    }

# ---- 2) 온보딩 서비스 ----
class OnboardingService:
    _sessions: Dict[str, Dict[str, Any]] = {}

    allowed_formats = {"wav", "mp3", "m4a"}
    content_type_map = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/aac": "m4a",
    }

    def _infer_format(self, audio_file: UploadFile) -> str:
        filename = (audio_file.filename or "").lower()
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in self.allowed_formats:
            return ext
        ct = (audio_file.content_type or "").lower().strip()
        return self.content_type_map.get(ct, "")

    def create_session(self, user_id: str, prompt_text: str) -> Dict[str, Any]:
        session_id = f"onb_{uuid.uuid4().hex}"
        settings.ONBOARDING_DIR.mkdir(parents=True, exist_ok=True)

        self._sessions[session_id] = {
            "userId": user_id,
            "promptText": prompt_text,
            "audioPath": None,
            "createdAt": _now_iso(),
        }
        return {"sessionId": session_id, "promptText": prompt_text, "createdAt": self._sessions[session_id]["createdAt"]}

    async def upload_audio(self, session_id: str, audio_file: UploadFile) -> Dict[str, Any]:
        sess = self._sessions.get(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="onboarding session not found")

        fmt = self._infer_format(audio_file)
        if fmt not in self.allowed_formats:
            raise HTTPException(status_code=400, detail='audio must be wav/mp3/m4a')

        save_dir = settings.ONBOARDING_DIR / session_id
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"pronunciation.{fmt}"

        with save_path.open("wb") as f:
            while True:
                chunk = await audio_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        sess["audioPath"] = str(save_path)
        sess["uploadedAt"] = _now_iso()
        return {"sessionId": session_id, "filePath": str(save_path), "uploadedAt": sess["uploadedAt"]}

    async def finalize(self, session_id: str, stt_func) -> Dict[str, Any]:
        """
        stt_func: async (audio_path:str) -> str
        - 기존 Deepgram/OpenAI STTService를 여기로 주입해서 재사용
        """
        sess = self._sessions.get(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="onboarding session not found")
        if not sess.get("audioPath"):
            raise HTTPException(status_code=400, detail="no audio uploaded")

        expected = sess["promptText"]
        recognized = await stt_func(sess["audioPath"])   # <-- 여기서 실제 STT 호출
        stats = compute_error_pattern(expected, recognized)

        settings.PERSONA_DIR.mkdir(parents=True, exist_ok=True)
        persona_path = settings.PERSONA_DIR / f"{sess['userId']}.json"

        payload = {
            "userId": sess["userId"],
            "createdAt": _now_iso(),
            "expectedText": expected,
            "recognizedText": recognized,
            "stats": stats,
        }
        persona_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "sessionId": session_id,
            "userId": sess["userId"],
            "personaPath": str(persona_path),
            "recognizedText": recognized,
            "stats": stats,
            "createdAt": payload["createdAt"],
        }
    
    def finalize_with_recognized_text(self, session_id: str, recognized_text: str) -> dict:
        sess = self._sessions.get(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="onboarding session not found")

        expected = sess["promptText"]
        stats = compute_error_pattern(expected, recognized_text)

        settings.PERSONA_DIR.mkdir(parents=True, exist_ok=True)
        persona_path = settings.PERSONA_DIR / f"{sess['userId']}.json"

        payload = {
            "userId": sess["userId"],
            "createdAt": _now_iso(),
            "expectedText": expected,
            "recognizedText": recognized_text,
            "stats": stats,
        }
        persona_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "sessionId": session_id,
            "userId": sess["userId"],
            "personaPath": str(persona_path),
            "recognizedText": recognized_text,
            "stats": stats,
            "createdAt": payload["createdAt"],
        }
