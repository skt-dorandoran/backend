from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from schemas.crisis_schema import (
    ComprehensionCheckRequest,
    ComprehensionCheckResponse,
)


# 이해 실패 키워드 리스트
COMPREHENSION_FAILURE_KEYWORDS = [
    # 네?/예? 계열
    "네?", "예?", "어?", "응?", "엉?", "어어?", "네네?",

    # 뭐? 계열
    "뭐?", "뭔데?", "뭐라고?", "뭐라구?", "뭐라는거야?", "뭐래?", "뭐라", "뭐예요?",
    "뭐라고요?", "뭐라구요?", "뭐라는 거예요?", "뭐라시는 거예요?",
    "뭡니까?", "뭐라는 겁니까?", "뭐라 하셨어요?", "뭐라셨어요?",

    # 안 들려요 계열
    "안 들려요", "잘 안 들려요", "안 들렸어요", "잘 안 들렸어요",
    "못 들었어요", "못 들었는데요", "잘 못 들었어요", "잘 못 들었는데요",
    "안 들리는데요", "잘 안 들리는데요", "소리가 안 들려요", "목소리가 안 들려요",
    "잘 안 들리네요", "소리가 작아요", "목소리가 작아요", "끊겨요", "끊기네요",

    # 다시 계열
    "다시", "다시요?", "다시요", "한번만 다시", "다시 한번",
    "다시 말해주세요", "다시 말씀해주세요", "다시 얘기해주세요", "다시 말해줘요", "다시 말해 줄래요?",
    "다시 말씀해 주세요", "다시 한 번 말씀해주세요", "다시 한번 말해주세요",
    "한 번 더", "한번 더", "다시 한 번만", "다시 한번만",
    "한 번만 더", "한번만 더", "다시 한 번 말해줘요", "다시 한번 말해줘요",
    "다시 설명해주세요", "다시 얘기해 주세요",

    # 무슨 계열
    "무슨?", "무슨 말?", "무슨 말이야?", "무슨 말이에요?", "무슨 말씀?",
    "무슨 말씀이세요?", "무슨 말씀이신가요?", "무슨 말씀이십니까?",
    "무슨 얘기세요?", "무슨 얘기예요?", "무슨 뜻?", "무슨 뜻이에요?",
    "무슨 뜻이세요?", "무슨 뜻인가요?", "무슨 의미예요?", "무슨 의미세요?",

    # 이해가 계열
    "이해가", "이해 못했어요", "이해 못 했어요", "이해를 못했어요",
    "이해가 안 가요", "이해가 안 돼요", "이해가 안되요", "이해 안 돼요",
    "이해 못하겠어요", "이해를 못하겠어요", "잘 이해가 안 가요",
    "이해가 잘 안 가요", "이해가 잘 안되네요", "이해가 어려워요",

    # 못 알아들었어요 계열
    "무슨 소리예요?", "무슨 소리세요?", "무슨 소리야?",
    "못 알아들었어요", "못 알아들었는데요", "잘 못 알아들었어요",
    "알아듣지 못했어요", "잘 못 알아들었는데요",

    # 모르겠어요 계열
    "잘 모르겠어요", "잘 모르겠는데요", "잘 모르겠네요",
    "무슨 말인지", "무슨 말인지 모르겠어요", "무슨 말씀인지 모르겠어요",

    # 그게 무슨 계열
    "그게 무슨", "그게 무슨 말이에요?", "그게 무슨 뜻이에요?",
    "그게 무슨 의미예요?", "그게 뭔 말이에요?",

    # 천천히/크게
    "천천히", "천천히 말해주세요", "천천히 말씀해주세요",
    "천천히 얘기해주세요", "좀 천천히", "좀 천천히 말해주세요",
    "크게", "크게 말해주세요", "크게 말씀해주세요", "좀 크게",
    "소리 좀 크게", "목소리 좀 크게"
]


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso_timestamp(timestamp_str: str) -> datetime:
    """ISO 8601 타임스탬프를 datetime 객체로 변환"""
    # Z를 +00:00으로 변환
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str[:-1] + '+00:00'
    return datetime.fromisoformat(timestamp_str)


class CrisisService:
    # callId별 상태 저장 (인메모리)
    _call_states: Dict[str, Dict[str, Any]] = {}

    # 설정값
    FAILURE_THRESHOLD = 3  # 임계값
    DUPLICATE_WINDOW_SECONDS = 10  # 중복 검사 시간 (초)
    RESET_TIMEOUT_SECONDS = 120  # 2분간 미감지 시 리셋

    def _get_or_create_call_state(self, call_id: str) -> Dict[str, Any]:
        """callId에 대한 상태를 가져오거나 새로 생성"""
        if call_id not in self._call_states:
            self._call_states[call_id] = {
                "failure_count": 0,
                "last_keyword": None,
                "last_keyword_time": None,
                "last_activity_time": datetime.now(timezone.utc),
                "matched_keywords_history": [],
            }
        return self._call_states[call_id]

    def _check_and_reset_timeout(self, call_state: Dict[str, Any], current_time: datetime) -> None:
        """2분간 키워드 미감지 시 카운터 리셋"""
        last_activity = call_state.get("last_activity_time")
        if last_activity:
            time_diff = (current_time - last_activity).total_seconds()
            if time_diff >= self.RESET_TIMEOUT_SECONDS:
                # 리셋
                call_state["failure_count"] = 0
                call_state["last_keyword"] = None
                call_state["last_keyword_time"] = None
                call_state["matched_keywords_history"] = []

    def _find_matched_keywords(self, text: str) -> List[str]:
        """텍스트에서 매칭되는 키워드 찾기"""
        matched = []
        text_lower = text.lower().strip()

        for keyword in COMPREHENSION_FAILURE_KEYWORDS:
            if keyword in text_lower:
                matched.append(keyword)

        return matched

    def _is_duplicate_keyword(
        self,
        keyword: str,
        call_state: Dict[str, Any],
        current_time: datetime
    ) -> bool:
        """동일 키워드가 10초 이내에 재발화되었는지 확인"""
        last_keyword = call_state.get("last_keyword")
        last_keyword_time = call_state.get("last_keyword_time")

        if last_keyword == keyword and last_keyword_time:
            time_diff = (current_time - last_keyword_time).total_seconds()
            if time_diff <= self.DUPLICATE_WINDOW_SECONDS:
                return True

        return False

    async def check_comprehension(
        self,
        request: ComprehensionCheckRequest
    ) -> ComprehensionCheckResponse:
        """이해 실패 키워드 감지 및 처리"""

        # isFinal이 False인 경우 무시
        if not request.isFinal:
            call_state = self._get_or_create_call_state(request.callId)
            return ComprehensionCheckResponse(
                status="ok",
                callId=request.callId,
                keywordMatched=False,
                failureCount=call_state["failure_count"],
                threshold=self.FAILURE_THRESHOLD,
                timestamp=_utc_now_iso_z(),
            )

        # 타임스탬프 파싱
        try:
            current_time = _parse_iso_timestamp(request.timestamp)
        except Exception:
            current_time = datetime.now(timezone.utc)

        # 상태 가져오기
        call_state = self._get_or_create_call_state(request.callId)

        # 타임아웃 체크 및 리셋
        self._check_and_reset_timeout(call_state, current_time)

        # 키워드 매칭
        matched_keywords = self._find_matched_keywords(request.text)

        # 매칭 안 됨
        if not matched_keywords:
            call_state["last_activity_time"] = current_time
            return ComprehensionCheckResponse(
                status="ok",
                callId=request.callId,
                keywordMatched=False,
                failureCount=call_state["failure_count"],
                threshold=self.FAILURE_THRESHOLD,
                timestamp=_utc_now_iso_z(),
            )

        # 매칭됨 - 첫 번째 매칭 키워드 사용
        matched_keyword = matched_keywords[0]

        # 중복 검사
        is_duplicate = self._is_duplicate_keyword(matched_keyword, call_state, current_time)

        if is_duplicate:
            # 중복 감지 - 카운트 안 함
            call_state["last_activity_time"] = current_time
            return ComprehensionCheckResponse(
                status="ok",
                callId=request.callId,
                keywordMatched=True,
                matchedKeywords=[matched_keyword],
                duplicateDetected=True,
                failureCount=call_state["failure_count"],
                threshold=self.FAILURE_THRESHOLD,
                timestamp=_utc_now_iso_z(),
            )

        # 새로운 키워드 - 카운트 증가
        call_state["failure_count"] += 1
        call_state["last_keyword"] = matched_keyword
        call_state["last_keyword_time"] = current_time
        call_state["last_activity_time"] = current_time
        call_state["matched_keywords_history"].append({
            "keyword": matched_keyword,
            "time": current_time,
        })

        current_count = call_state["failure_count"]

        # 임계값 도달
        if current_count >= self.FAILURE_THRESHOLD:
            return ComprehensionCheckResponse(
                status="alert",
                callId=request.callId,
                keywordMatched=True,
                matchedKeywords=[matched_keyword],
                failureCount=current_count,
                threshold=self.FAILURE_THRESHOLD,
                enableAiCorrection=True,
                timestamp=_utc_now_iso_z(),
            )

        # 임계값 미도달
        return ComprehensionCheckResponse(
            status="monitoring",
            callId=request.callId,
            keywordMatched=True,
            matchedKeywords=[matched_keyword],
            failureCount=current_count,
            threshold=self.FAILURE_THRESHOLD,
            timestamp=_utc_now_iso_z(),
        )
