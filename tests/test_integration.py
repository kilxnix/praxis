"""End-to-end integration test — verifies the full pipeline works without Ollama."""
import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestFullFlow:
    def test_interview_then_mirror(self, client):
        """Complete flow: start -> interview -> check status -> switch to mirror."""
        with client.websocket_connect("/ws") as ws:
            # Start
            ws.send_json({"type": "start", "name": "IntegrationTest"})
            opening = ws.receive_json()
            assert opening["type"] == "opening"
            assert len(opening["text"]) > 0

            # Send a few messages
            for msg in [
                "I've been thinking about moving to a new city",
                "I love being around people but I also need my alone time",
                "Honestly I think I avoid conflict too much",
            ]:
                ws.send_json({"type": "message", "text": msg})
                resp = ws.receive_json()
                assert resp["type"] == "response"
                assert len(resp["text"]) > 0

            # Check status
            ws.send_json({"type": "command", "command": "status"})
            status = ws.receive_json()
            assert status["type"] == "status"
            assert "dimensions" in status["data"]
            assert len(status["data"]["dimensions"]) == 10

            # Switch to mirror mode
            ws.send_json({"type": "command", "command": "mirror"})
            mirror = ws.receive_json()
            assert mirror["type"] == "mode_change"
            assert mirror["mode"] == "mirror"
            assert len(mirror["text"]) > 0

            # Talk to the twin
            ws.send_json({"type": "message", "text": "What do you think about long distance?"})
            twin_resp = ws.receive_json()
            assert twin_resp["type"] == "response"
            assert twin_resp["mode"] == "mirror"
            assert len(twin_resp["text"]) > 0

            # Switch back
            ws.send_json({"type": "command", "command": "interview"})
            back = ws.receive_json()
            assert back["type"] == "mode_change"
            assert back["mode"] == "interview"
