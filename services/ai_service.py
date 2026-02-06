import json
import time
from datetime import datetime, timezone
from typing import List

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
상대방의 발화를 분석하고, 사용자가 선택할 수 있는 자연스럽고 다양한 답변 3개를 생성합니다.

# 답변 생성 원칙
- 3개의 답변은 각기 **다른 맥락이나 의도**를 가진 선택지
- 상황에 따라 다양한 관점에서 적절한 응답 제시
- 모든 답변은 동등한 가치를 가지며, 사용자가 상황에 맞게 선택

# 답변 예시
상대방: "무엇을 도와드릴까요?"
→ 답변1: "예약 시간 문의드려요."
→ 답변2: "진료확인서 발급 방법 알려주세요."
→ 답변3: "접수 마감이 몇시인가요?"

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

반드시 JSON 형식으로만 응답하세요.
"""

USER_PROMPT_TEMPLATE = """
# 대화 맥락
{conversation_context}

# 상대방의 발화
상대방: {user_speech}

# 요청
위 상황에서 사용자가 선택할 수 있는 **서로 다른 맥락의 적절한 답변 3개**를 생성해주세요.
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
    }},
    {{
      "id": "response_3",
      "text": "답변 텍스트",
      "tone": "casual",
      "priority": 3
    }}
  ]
}}
"""


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
