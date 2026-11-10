"""Health check."""
from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    return {"status": "ok", "chunks": request.app.state.index.count(), "llm": settings.LLM_PROVIDER,
            "answer_model": settings.ANSWER_MODEL}
