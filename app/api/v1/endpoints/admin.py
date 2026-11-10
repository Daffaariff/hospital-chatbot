"""Content refresh and content-gap reports (API key required)."""
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_store
from app.core.security import require_api_key
from app.ingest.__main__ import run_ingest
from app.services.store import Store

router = APIRouter(prefix="/admin", dependencies=[Depends(require_api_key)])


@router.post("/refresh")
def refresh(request: Request) -> dict:
    return run_ingest(index=request.app.state.index)


@router.get("/unanswered")
def unanswered(store: Store = Depends(get_store)) -> list[dict]:
    return store.list("unanswered")


@router.get("/leads")
def leads(store: Store = Depends(get_store)) -> list[dict]:
    return store.list("leads")
