"""Chat endpoint."""
from fastapi import APIRouter, Depends, HTTPException

from app.adapters.protocols import LLMRefusal
from app.api.deps import get_chat
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()
log = get_logger("api.chat")


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, svc: ChatService = Depends(get_chat)) -> ChatResponse:
    try:
        return svc.answer(req)
    except LLMRefusal:
        raise HTTPException(422, "The assistant can't help with that request.")
    except Exception as e:
        log.exception(f"chat failed: {e}")
        raise HTTPException(502, "The assistant is temporarily unavailable. Please try again.")
