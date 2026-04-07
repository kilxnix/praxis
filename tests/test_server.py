"""Tests for the FastAPI WebSocket server (interview mode)."""
import json
import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestStaticFiles:
    def test_index_page_loads(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestWebSocket:
    def test_start_session(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            data = ws.receive_json()
            assert data["type"] == "started"
            assert "greeting" in data
            assert "data" in data
            assert data["data"]["phase"] == "ARRIVAL"

    def test_send_message(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # started

            ws.send_json({"type": "message", "text": "I just moved to a new city."})
            data = ws.receive_json()
            assert data["type"] == "response"
            assert "text" in data
            assert "move" in data
            assert "data" in data

    def test_status_command(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()

            ws.send_json({"type": "status"})
            data = ws.receive_json()
            assert data["type"] == "status"
            assert "data" in data
            assert "readiness" in data["data"]

    def test_empty_message_ignored(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()

            ws.send_json({"type": "message", "text": ""})
            # Should not get a response for empty message
            ws.send_json({"type": "status"})
            data = ws.receive_json()
            assert data["type"] == "status"
