"""Chat endpoints: POST (whole answer) and WebSocket (streamed events)."""
from contextlib import aclosing

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from starlette.websockets import WebSocketState

from app.adapters.protocols import LLMRefusal
from app.api.deps import get_chat
from app.core.logging import get_logger
from app.core.messages import INVALID_MESSAGE, REFUSED, UNAVAILABLE
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()
log = get_logger("api.chat")


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, svc: ChatService = Depends(get_chat)) -> ChatResponse:
    try:
        return await svc.answer(req)
    except LLMRefusal:
        raise HTTPException(422, REFUSED)
    except Exception as e:
        log.exception(f"chat failed: {e}")
        raise HTTPException(502, UNAVAILABLE)


@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket):
    """Client sends a ChatRequest as JSON; server replies with status/delta/reset events and one final event."""
    await ws.accept()
    svc: ChatService = ws.app.state.chat
    try:
        while True:
            try:
                req = ChatRequest(**await ws.receive_json())
            except (ValidationError, ValueError, TypeError):
                await ws.send_json({"type": "error", "text": INVALID_MESSAGE})
                continue
            try:
                # NOTE: if the user leaves, send_json raises and aclosing stops the LLM stream we'd pay for
                async with aclosing(svc.stream(req)) as events:
                    async for event in events:
                        if event["type"] == "final":
                            event = {"type": "final", "response": event["response"].model_dump()}
                        await ws.send_json(event)
            except WebSocketDisconnect:
                raise
            except Exception as e:
                if ws.client_state != WebSocketState.CONNECTED:
                    return
                log.exception(f"chat stream failed: {e}")
                await ws.send_json({"type": "error", "text": UNAVAILABLE})
    except WebSocketDisconnect:
        pass
