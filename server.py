"""
Vib -- FastAPI Server (Wellness Companion)

WebSocket-based server for the Vib wellness companion.
Serves the static frontend and manages per-connection sessions.

Modes:
- Conversation: Vib gets to know you through conversation
- Mirror: Chat with your companion in voice-matching mode
- Logging: Track meals, mood, sleep, movement, social activity

Run: uvicorn server:app --reload
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from interviewer.orchestrator import VibSession
from interviewer.llm_client import OllamaLLMClient, ModelTier
from interviewer.persona_builder import build_soul_persona
from interviewer.storage import SoulStorage
from vib_wellness.logging_service import log_entry, entry_to_evidence
from vib_wellness.post_binge import enter_acute_mode, check_mode_transition

app = FastAPI(title="Vib -- Wellness Companion")

# Persistent soul storage -- lives across all connections
_storage = SoulStorage(db_path=str(Path(__file__).parent / "souls.db"))

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


def _create_llm_client():
    """Create an Ollama client. Returns None if Ollama isn't reachable."""
    import httpx

    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        resp.raise_for_status()
        data = resp.json()
        available = {m["name"].split(":")[0] for m in data.get("models", [])}
        available.update(m["name"] for m in data.get("models", []))
        required_model = ModelTier.INTERVIEWER
        if required_model not in available and required_model.split(":")[0] not in available:
            print(f"[WARN] Model {required_model} not found. Available: {available}")
            return None
        return OllamaLLMClient()
    except Exception as e:
        print(f"[WARN] Ollama not reachable: {e}")
        return None


def _serialize_session(session: VibSession) -> dict:
    """Serialize session state for the frontend."""
    readiness = session.get_soul_readiness()
    return {
        "phase": session.graph.phase.name,
        "turn": session.graph.turn_number,
        "session": session.graph.session_number,
        "attunement": round(session.graph.attunement_confidence, 2),
        "temperature": session.graph.temperature.value,
        "energy": round(session.graph.energy_level, 2),
        "readiness": readiness,
        "post_binge_mode": session.cartographer.post_binge_mode,
    }


@app.post("/upload/photo")
async def upload_photo(file: UploadFile = File(...)):
    """Accept a photo upload, return an ID for referencing in log messages."""
    import uuid
    photo_id = str(uuid.uuid4())
    upload_dir = Path(__file__).parent / "uploads"
    upload_dir.mkdir(exist_ok=True)
    path = upload_dir / f"{photo_id}.jpg"
    content = await file.read()
    path.write_bytes(content)
    return {"photo_id": photo_id, "size": len(content)}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    session = None
    llm_client = None
    mirror_mode = False

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start":
                llm_client = _create_llm_client()
                name = msg.get("name", "").strip() or None
                session = VibSession(
                    user_name=name,
                    llm_client=llm_client,
                    storage=_storage if name else None,
                )
                mirror_mode = False

                # Send initial greeting
                if llm_client:
                    try:
                        result = await session.process_turn(
                            "[User has just joined the conversation]"
                        )
                        # Remove the synthetic message from history
                        session.conversation_history = session.conversation_history[-1:]
                        greeting = result["response"]
                    except Exception as e:
                        print(f"[WARN] LLM greeting failed: {e}")
                        llm_client = None
                        session.llm_client = None
                        greeting = "Hey. What's on your mind?"
                else:
                    greeting = "Hey. What's on your mind?"

                returning = (
                    session.storage is not None
                    and session.graph.session_number > 1
                )

                await ws.send_json({
                    "type": "started",
                    "greeting": greeting,
                    "data": _serialize_session(session),
                    "has_llm": llm_client is not None,
                    "returning": returning,
                    "session_number": session.graph.session_number,
                })

            elif msg_type == "message" and session and not mirror_mode:
                text = msg.get("text", "").strip()
                if not text:
                    continue

                try:
                    result = await session.process_turn(text)
                except Exception as e:
                    print(f"[ERROR] process_turn failed: {e}")
                    # Retry without LLM
                    llm_client = None
                    session.llm_client = None
                    result = await session.process_turn(text)

                await ws.send_json({
                    "type": "response",
                    "text": result["response"],
                    "move": result["move"].move_type.value,
                    "data": _serialize_session(session),
                })

            elif msg_type == "status" and session:
                await ws.send_json({
                    "type": "status",
                    "data": _serialize_session(session),
                })

            elif msg_type == "enter_mirror" and session:
                readiness = session.get_soul_readiness()
                if not llm_client:
                    await ws.send_json({
                        "type": "error",
                        "message": "Mirror mode requires an LLM connection.",
                    })
                    continue

                mirror_mode = True
                persona = build_soul_persona(
                    name=session.user_name or "User",
                    cartographer=session.cartographer,
                    conversation_history=session.conversation_history,
                )

                await ws.send_json({
                    "type": "mirror_started",
                    "data": _serialize_session(session),
                })

            elif msg_type == "mirror_message" and session and mirror_mode:
                text = msg.get("text", "").strip()
                if not text:
                    continue

                # Enhanced mirror — include evidence for voice fidelity
                evidence = None
                if session.storage and session.soul_id:
                    evidence = _storage.load_evidence(session.soul_id)

                persona = build_soul_persona(
                    name=session.user_name or "User",
                    cartographer=session.cartographer,
                    conversation_history=session.conversation_history,
                    evidence=evidence,
                )

                try:
                    response = await llm_client.mirror_generate(
                        system=persona,
                        messages=[{"role": "user", "content": text}],
                    )
                except Exception as e:
                    print(f"[ERROR] mirror_generate failed: {e}")
                    response = "I'm having trouble finding the words right now."

                await ws.send_json({
                    "type": "mirror_response",
                    "text": response,
                })

            elif msg_type == "exit_mirror" and session:
                mirror_mode = False
                await ws.send_json({
                    "type": "mirror_exited",
                    "data": _serialize_session(session),
                })

            elif msg_type == "list_souls":
                # List all souls that exist in storage
                rows = _storage.db.execute(
                    "SELECT s.name, ss.trust_score, ss.phase, "
                    "(SELECT COUNT(*) FROM sessions WHERE soul_id = s.id) as sessions, "
                    "(SELECT COUNT(*) FROM trait_evidence WHERE soul_id = s.id) as evidence "
                    "FROM souls s "
                    "JOIN soul_state ss ON s.id = ss.soul_id "
                    "ORDER BY s.updated_at DESC"
                ).fetchall()
                souls = [
                    {
                        "name": r[0],
                        "trust": round(r[1], 2),
                        "phase": r[2],
                        "sessions": r[3],
                        "evidence_count": r[4],
                    }
                    for r in rows
                ]
                await ws.send_json({
                    "type": "soul_list",
                    "souls": souls,
                })

            # ─────────────────────────────────────
            # WELLNESS LOGGING
            # ─────────────────────────────────────

            elif msg_type and msg_type.startswith("log_") and session:
                kind = msg_type[4:]  # "log_meal" -> "meal"
                payload = msg.get("payload", {})

                if not session.soul_id:
                    await ws.send_json({
                        "type": "error",
                        "message": "Log entries require a named session.",
                    })
                    continue

                try:
                    source = "manual"
                    at_time = None
                    if isinstance(payload, dict):
                        source = payload.pop("source", "manual")
                        at_time = payload.pop("at", None)

                    entry_id = log_entry(
                        storage=_storage,
                        soul_id=session.soul_id,
                        kind=kind,
                        payload=payload,
                        source=source,
                        at=at_time,
                    )

                    # Generate evidence signals from the entry
                    signals = entry_to_evidence(kind, payload)
                    if signals and session.session_id:
                        _storage.save_evidence(
                            session.soul_id, session.session_id,
                            session.graph.turn_number, signals,
                            f"[logged {kind}]",
                        )

                    # If binge_marker, enter acute mode
                    if kind == "binge_marker":
                        enter_acute_mode(session.cartographer)

                    await ws.send_json({
                        "type": "entry_logged",
                        "payload": {"entry_id": entry_id},
                    })

                except ValueError as e:
                    await ws.send_json({
                        "type": "error",
                        "message": str(e),
                    })

    except WebSocketDisconnect:
        pass
    finally:
        if llm_client:
            await llm_client.close()
