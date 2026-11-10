"""v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import admin, chat, health, leads

api_router = APIRouter()
for r, tag in ((health.router, "health"), (chat.router, "chat"), (leads.router, "leads"), (admin.router, "admin")):
    api_router.include_router(r, tags=[tag])
