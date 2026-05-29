from fastapi import APIRouter, Depends
from app.security import require_api_key
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import answer

router = APIRouter(prefix="/api/v1/projects", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    return await answer(req.project_id, req.user_question)
