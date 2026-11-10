"""Chat endpoints: POST (whole answer) and WebSocket (streamed events)."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.adapters.protocols import LLMRefusal
from app.api.deps import get_chat
from app.core.logging import get_logger
from app.core.messages import INVALID_MESSAGE, REFUSED, UNAVAILABLE
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()
log = get_logger("api.chat")


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, svc: ChatService = Depends(get_chat)) -> ChatResponse:
    try:
        return svc.answer(req)
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
    loop = asyncio.get_running_loop()
    try:
        while True:
            try:
                req = ChatRequest(**await ws.receive_json())
            except (ValidationError, ValueError, TypeError):
                await ws.send_json({"type": "error", "text": INVALID_MESSAGE})
                continue
            queue: asyncio.Queue = asyncio.Queue()

            def run() -> None:
                # NOTE: the pipeline is sync (SDK streaming), so it runs in a thread and hands events to the socket
                try:
                    for event in svc.stream(req):
                        if event["type"] == "final":
                            event = {"type": "final", "response": event["response"].model_dump()}
                        loop.call_soon_threadsafe(queue.put_nowait, event)
                except Exception as e:
                    log.exception(f"chat stream failed: {e}")
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "text": UNAVAILABLE})
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            worker = asyncio.create_task(asyncio.to_thread(run))
            while (event := await queue.get()) is not None:
                await ws.send_json(event)
            await worker
    except WebSocketDisconnect:
        pass
