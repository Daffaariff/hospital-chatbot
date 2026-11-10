"""Shared singletons, created once in the app lifespan."""
from fastapi import Request

from app.services.chat_service import ChatService
from app.services.store import Store


def get_chat(request: Request) -> ChatService:
    return request.app.state.chat


def get_store(request: Request) -> Store:
    return request.app.state.store
