"""Tests for the FastAPI WebSocket server."""
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
            assert data["type"] == "opening"
            assert "text" in data

    def test_send_message(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # opening

            ws.send_json({"type": "message", "text": "I love hiking"})
            data = ws.receive_json()
            assert data["type"] == "response"
            assert "text" in data

    def test_status_command(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # opening

            ws.send_json({"type": "command", "command": "status"})
            data = ws.receive_json()
            assert data["type"] == "status"
            assert "data" in data
            assert "dimensions" in data["data"]

    def test_mirror_mode(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "name": "TestUser"})
            ws.receive_json()  # opening

            ws.send_json({"type": "command", "command": "mirror"})
            data = ws.receive_json()
            assert data["type"] == "mode_change"
            assert data["mode"] == "mirror"
