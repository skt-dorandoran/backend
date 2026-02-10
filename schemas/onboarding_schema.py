from pydantic import BaseModel
from typing import Optional, Dict, List, Any

class CreateOnboardingSessionResponse(BaseModel):
    sessionId: str
    promptText: str
    createdAt: str

class UploadOnboardingAudioResponse(BaseModel):
    sessionId: str
    filePath: str
    uploadedAt: str

class FinalizeOnboardingResponse(BaseModel):
    sessionId: str
    userId: str
    personaPath: str
    recognizedText: str
    stats: Dict[str, Any]
    createdAt: str
