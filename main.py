from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.settings import settings

app = FastAPI(
    title="Backend API Server",
    description="API server for handling backend requests",
    version="1.0.0"
)

# 라우터 여기에 추가
# app.include_router(xxx_router.router)

# 설정값 출력 (디버깅용)
# print(settings.ENV)
# print(settings.DNS_API_TOKEN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인에서 요청 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

@app.get("/")
def main():
    return "Hello World!"
