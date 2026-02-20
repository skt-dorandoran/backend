import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import AsyncIterator, List

from openai import AsyncOpenAI

from core.settings import settings
from schemas.ai_schema import (
    ConversationMessage,
    GenerateResponseRequest,
    GenerateResponseResponse,
    ResponseItem,
)


SYSTEM_PROMPT = """
당신은 청각 장애인을 위한 실시간 통화 어시스턴트입니다.
상대방의 발화를 분석하고, 사용자가 선택할 수 있는 자연스럽고 다양한 답변 2개를 생성합니다.

# 답변 생성 원칙
- 2개의 답변은 각기 **다른 맥락이나 의도**를 가진 선택지
- 상황에 따라 다양한 관점에서 적절한 응답 제시
- 모든 답변은 동등한 가치를 가지며, 사용자가 상황에 맞게 선택

# 답변 예시
상대방: "무엇을 도와드릴까요?"
→ 답변1: "예약 시간 문의드려요."
→ 답변2: "진료확인서 발급 방법 알려주세요."

# 답변 특징
- 짧고 명확하게 (1-2문장)
- 자연스러운 한국어 구어체
- 각 답변은 서로 다른 요구사항이나 질문 표현
- 상황에 맞는 적절한 톤

# 톤 가이드
- friendly: 친근하고 따뜻한 톤
- formal: 정중하고 격식있는 톤
- casual: 편안하고 자연스러운 톤
- professional: 업무적이고 전문적인 톤
- polite: 공손하고 예의바른 톤

반드시 JSON 형식으로만 응답하세요.
"""

USER_PROMPT_TEMPLATE = """
# 대화 맥락
{conversation_context}

# 상대방의 발화
상대방: {user_speech}

# 요청
위 상황에서 사용자가 선택할 수 있는 **서로 다른 맥락의 적절한 답변 2개**를 생성해주세요.
각 답변은 다른 의도나 질문을 담아야 합니다.

JSON 형식:
{{
  "responses": [
    {{
      "id": "response_1",
      "text": "답변 텍스트",
      "tone": "friendly",
      "priority": 1
    }},
    {{
      "id": "response_2",
      "text": "답변 텍스트",
      "tone": "formal",
      "priority": 2
    }}
  ]
}}
"""


def _utc_now_iso_z() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()


def _build_conversation_context(history: List[ConversationMessage]) -> str:
    if not history:
        return "(대화 시작)"

    role_map = {"other": "상대방", "user": "나"}
    lines = [f"{role_map[msg.role]}: {msg.text}" for msg in history]
    return "\n".join(lines)


class AIService:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_response(self, request: GenerateResponseRequest) -> GenerateResponseResponse:
        start_time = time.time()

        conversation_context = _build_conversation_context(request.conversationHistory)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            conversation_context=conversation_context,
            user_speech=request.userSpeech,
        )

        completion = await self._client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
            max_tokens=500,
        )

        raw = json.loads(completion.choices[0].message.content)

        responses = [
            ResponseItem(
                id=item["id"],
                text=item["text"],
                tone=item["tone"],
                priority=item["priority"],
            )
            for item in raw["responses"]
        ]

        processing_time = round(time.time() - start_time, 3)

        return GenerateResponseResponse(
            callId=request.callId,
            responses=responses,
            generatedAt=_utc_now_iso_z(),
            processingTime=processing_time,
        )

    async def generate_response_stream(self, request: GenerateResponseRequest) -> AsyncIterator[bytes]:
        start_time = time.time()
        generated_at = _utc_now_iso_z()

        conversation_context = _build_conversation_context(request.conversationHistory)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            conversation_context=conversation_context,
            user_speech=request.userSpeech,
        )

        stream = await self._client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
            max_tokens=500,
            stream=True,
        )

        # Keep output schema identical to static response while streaming
        # the "responses" array content as it is generated.
        prefix = (
            "{"
            + f"\"callId\":{json.dumps(request.callId, ensure_ascii=False)},"
            + "\"responses\":"
        )
        yield prefix.encode("utf-8")

        chunks: list[str] = []
        pre_array_buf = ""
        emitted_array = ""
        array_started = False
        array_done = False
        depth = 0
        in_string = False
        escaped = False

        def feed_array_char(ch: str) -> str:
            nonlocal depth, in_string, escaped, array_done, emitted_array
            if array_done:
                return ""

            out = ch
            emitted_array += ch

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == "\"":
                    in_string = False
                return out

            if ch == "\"":
                in_string = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    array_done = True
            return out

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
                out_chars: list[str] = []
                if not array_started:
                    pre_array_buf += delta
                    key_idx = pre_array_buf.find("\"responses\"")
                    if key_idx != -1:
                        array_idx = pre_array_buf.find("[", key_idx)
                        if array_idx != -1:
                            array_started = True
                            for ch in pre_array_buf[array_idx:]:
                                piece = feed_array_char(ch)
                                if piece:
                                    out_chars.append(piece)
                                if array_done:
                                    break
                            pre_array_buf = ""
                else:
                    for ch in delta:
                        piece = feed_array_char(ch)
                        if piece:
                            out_chars.append(piece)
                        if array_done:
                            break

                if out_chars:
                    yield "".join(out_chars).encode("utf-8")

        raw_text = "".join(chunks)
        raw = json.loads(raw_text)
        responses_raw = raw.get("responses", [])
        responses = [
            ResponseItem(
                id=item["id"],
                text=item["text"],
                tone=item["tone"],
                priority=item["priority"],
            )
            for item in responses_raw
        ]
        normalized_array = json.dumps([item.model_dump() for item in responses], ensure_ascii=False)
        if not array_started:
            yield normalized_array.encode("utf-8")
        elif not array_done and normalized_array.startswith(emitted_array):
            yield normalized_array[len(emitted_array):].encode("utf-8")

        processing_time = round(time.time() - start_time, 3)
        suffix = (
            ","
            + f"\"generatedAt\":{json.dumps(generated_at, ensure_ascii=False)},"
            + f"\"processingTime\":{processing_time}"
            + "}"
        )
        yield suffix.encode("utf-8")
