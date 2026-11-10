"""Health check."""
from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    return {"status": "ok", "chunks": len(request.app.state.index.chunks), "llm": settings.LLM_PROVIDER,
            "answer_model": settings.ANSWER_MODEL}
