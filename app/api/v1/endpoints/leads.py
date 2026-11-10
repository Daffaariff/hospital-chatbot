"""Lead capture."""
from fastapi import APIRouter, Depends

from app.api.deps import get_store
from app.schemas.chat import LeadRequest
from app.services.store import Store

router = APIRouter()


@router.post("/leads")
def create_lead(lead: LeadRequest, store: Store = Depends(get_store)) -> dict:
    store.add_lead(lead.name, lead.email, lead.question)
    return {"ok": True}
