from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ChatResponse


class StubChat:
    def stream(self, req):
        yield {"type": "status", "text": "Searching our pages…"}
        yield {"type": "delta", "text": "It costs $18,995. "}
        yield {"type": "final", "response": ChatResponse(answer="It costs $18,995.", answered=True, intent="price")}


def test_ws_streams_events_then_final():
    app.state.chat = StubChat()  # NOTE: no `with` -> lifespan (index, LLM) is not started
    with TestClient(app).websocket_connect("/api/v1/ws/chat") as ws:
        ws.send_json({"message": "cost?", "history": []})
        types = []
        while True:
            ev = ws.receive_json()
            types.append(ev["type"])
            if ev["type"] == "final":
                assert ev["response"]["answer"] == "It costs $18,995."
                break
        assert types == ["status", "delta", "final"]
        ws.send_json({"message": ""})
        assert ws.receive_json()["type"] == "error"
