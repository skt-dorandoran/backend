from fastapi import APIRouter, HTTPException

from schemas.crisis_schema import (
    ComprehensionCheckRequest,
    ComprehensionCheckResponse,
    ComprehensionCheckErrorResponse,
)
from services.crisis_service import CrisisService

router = APIRouter(prefix="/api/v1/crisis", tags=["crisis"])
crisis_service = CrisisService()


@router.post("/comprehension-check", response_model=ComprehensionCheckResponse)
async def comprehension_check(request: ComprehensionCheckRequest):
    """
    STT 결과에서 이해 실패 키워드를 감지하고, 3회 누적 시 AI 교정 모드 전환 플래그를 반환

    - isFinal: true 만 처리
    - 이해 실패 키워드 매칭 수행
    - 중복 검사 (동일 키워드 10초 이내 재발화 시 제외)
    - 키워드 매칭 시 카운터 +1
    - 카운터 ≥ 3 도달 시: enableAiCorrection: true 플래그 전송
    - 2분간 추가 키워드 미감지 시 카운터 자동 리셋
    """
    try:
        # callId 검증
        if not request.callId or not request.callId.strip():
            return ComprehensionCheckErrorResponse(
                status="error",
                code="INVALID_CALL_ID",
                message="유효하지 않은 통화 ID"
            )

        return await crisis_service.check_comprehension(request)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
