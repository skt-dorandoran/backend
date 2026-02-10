from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.settings import settings
from routers import onboarding_router, stt_router, voice_router, ai_router, crisis_router

app = FastAPI(
    title="Backend API Server",
    description="API server for handling backend requests",
    version="1.0.0"
)

# 라우터 여기에 추가
# app.include_router(xxx_router.router)
app.include_router(stt_router.router)
app.include_router(voice_router.router)
app.include_router(ai_router.router)
app.include_router(crisis_router.router)
app.include_router(onboarding_router.router)

# 설정값 출력 (디버깅용)
# print(settings.ENV)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인에서 요청 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

@app.get("/")
def main():
    return "Goodbye Everyone, Hello SKT FLY AI!"


# ==============================
# Local Test APIs
# ==============================

# 테스트용 정적 파일 제공: 기존 @app.get("/") 대체
# from fastapi.responses import FileResponse

# @app.get("/")
# async def get_test_page():
#     return FileResponse("tools/index.html")