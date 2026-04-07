"""End-to-end integration test -- full interview flow without Ollama."""
import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestFullFlow:
    def test_start_and_chat(self, client):
        """Complete flow: start -> messages -> status."""
        with client.websocket_connect("/ws") as ws:
            # Start session
            ws.send_json({"type": "start", "name": "TestUser"})
            started = ws.receive_json()
            assert started["type"] == "started"
            assert started["data"]["phase"] == "ARRIVAL"

            # Send messages
            ws.send_json({"type": "message", "text": "I just moved to a new city last month."})
            resp1 = ws.receive_json()
            assert resp1["type"] == "response"
            assert len(resp1["text"]) > 0
            assert resp1["data"]["turn"] == 2  # turn 1 was the synthetic greeting

            # Send another message
            ws.send_json({"type": "message", "text": "Yeah it's been an adjustment."})
            resp2 = ws.receive_json()
            assert resp2["type"] == "response"

            # Check status
            ws.send_json({"type": "status"})
            status = ws.receive_json()
            assert status["type"] == "status"
            assert "readiness" in status["data"]

    def test_attunement_increases_over_conversation(self, client):
        """Attunement should increase over multiple turns."""
        import uuid
        unique_name = f"AttTest_{uuid.uuid4().hex[:8]}"
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": unique_name})
            started = ws.receive_json()
            initial_attunement = started["data"]["attunement"]

            for msg in [
                "I love hiking in the mountains",
                "It makes me feel alive",
                "I've always been drawn to nature",
            ]:
                ws.send_json({"type": "message", "text": msg})
                ws.receive_json()

            ws.send_json({"type": "status"})
            status = ws.receive_json()
            assert status["data"]["attunement"] > initial_attunement
