from fastapi import APIRouter, HTTPException

from schemas.ai_schema import GenerateResponseRequest, GenerateResponseResponse
from services.ai_service import AIService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
ai_service = AIService()


@router.post("/generate-response", response_model=GenerateResponseResponse)
async def generate_response(request: GenerateResponseRequest):
    try:
        return await ai_service.generate_response(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
