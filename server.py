"""
Vib -- FastAPI Server (Agentic Dating)

WebSocket-based server for The Soul interviewer and the Vib World.
Serves the static frontend and manages per-connection sessions.

Modes:
- Interview: The Soul gets to know you through conversation
- Mirror: Chat with your digital twin once enough data is collected
- Vib: Two souls meet autonomously and the system evaluates compatibility

Run: uvicorn server:app --reload
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from interviewer.orchestrator import VibSession
from interviewer.llm_client import OllamaLLMClient, ModelTier
from interviewer.persona_builder import build_soul_persona
from interviewer.storage import SoulStorage

app = FastAPI(title="Vib -- Agentic Dating")

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
    }


def _load_soul_for_vib(name: str) -> dict:
    """
    Load all data needed to represent a soul in the vib world.
    Returns None if soul doesn't exist or isn't ready.
    """
    soul_data = _storage.load_soul(name)
    if not soul_data:
        return None

    soul_id = soul_data["soul_id"]
    evidence = _storage.load_evidence(soul_id)

    return {
        "name": name,
        "soul_id": soul_id,
        "cartographer": soul_data["cartographer"],
        "conversation_history": soul_data["messages"],
        "evidence": evidence,
    }


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

            # ─────────────────────────────────────
            # VIB WORLD
            # ─────────────────────────────────────

            elif msg_type == "start_vib":
                soul_a_name = msg.get("soul_a", "").strip()
                soul_b_name = msg.get("soul_b", "").strip()

                if not soul_a_name or not soul_b_name:
                    await ws.send_json({
                        "type": "error",
                        "message": "Need two soul names to start a vib.",
                    })
                    continue

                if soul_a_name == soul_b_name:
                    await ws.send_json({
                        "type": "error",
                        "message": "Can't vib with yourself.",
                    })
                    continue

                # Ensure LLM is available
                if not llm_client:
                    llm_client = _create_llm_client()
                if not llm_client:
                    await ws.send_json({
                        "type": "error",
                        "message": "Vib requires an LLM connection. Is Ollama running?",
                    })
                    continue

                # Load both souls
                soul_a = _load_soul_for_vib(soul_a_name)
                soul_b = _load_soul_for_vib(soul_b_name)

                if not soul_a:
                    await ws.send_json({
                        "type": "error",
                        "message": f"Soul '{soul_a_name}' not found. They need to be interviewed first.",
                    })
                    continue
                if not soul_b:
                    await ws.send_json({
                        "type": "error",
                        "message": f"Soul '{soul_b_name}' not found. They need to be interviewed first.",
                    })
                    continue

                # Create vib session in storage
                vib_db_id = _storage.create_vib_session(
                    soul_a["soul_id"], soul_b["soul_id"]
                )

                # Notify client that vib is starting
                await ws.send_json({
                    "type": "vib_started",
                    "vib_id": vib_db_id,
                    "soul_a": soul_a_name,
                    "soul_b": soul_b_name,
                })

                # Configure and run the vib
                config = VibConfig(
                    max_turns=msg.get("max_turns", 20),
                )

                vib_session = VibSession(
                    soul_a=soul_a,
                    soul_b=soul_b,
                    llm_client=llm_client,
                    config=config,
                )

                # Stream turns to client and persist each one
                async def on_vib_turn(turn_data):
                    # Persist the turn
                    speaker_name = turn_data["speaker"]
                    speaker_soul_id = (
                        soul_a["soul_id"] if speaker_name == soul_a_name
                        else soul_b["soul_id"]
                    )
                    _storage.save_vib_message(
                        vib_db_id,
                        turn_data["turn"],
                        speaker_soul_id,
                        turn_data["content"],
                        turn_data["phase"],
                    )

                    # Stream to client
                    await ws.send_json({
                        "type": "vib_turn",
                        "vib_id": vib_db_id,
                        "turn": turn_data["turn"],
                        "speaker": turn_data["speaker"],
                        "content": turn_data["content"],
                        "phase": turn_data["phase"],
                    })

                try:
                    result = await vib_session.run(on_turn=on_vib_turn)

                    # Persist result
                    _storage.complete_vib_session(vib_db_id, result.turns_completed)
                    _storage.save_vib_result(vib_db_id, {
                        "compatibility_score": result.compatibility_score,
                        "recommendation": result.recommendation.value,
                        "dimension_scores": result.dimension_scores,
                        "key_moments": [
                            {
                                "turn": m.turn,
                                "type": m.moment_type,
                                "description": m.description,
                                "speaker": m.speaker,
                            }
                            for m in result.key_moments
                        ],
                        "summary": result.summary,
                        "soul_a_verdict": result.soul_a_verdict,
                        "soul_b_verdict": result.soul_b_verdict,
                    })

                    # Send final result
                    await ws.send_json({
                        "type": "vib_result",
                        "vib_id": vib_db_id,
                        "compatibility_score": result.compatibility_score,
                        "recommendation": result.recommendation.value,
                        "dimension_scores": result.dimension_scores,
                        "summary": result.summary,
                        "soul_a_verdict": result.soul_a_verdict,
                        "soul_b_verdict": result.soul_b_verdict,
                        "key_moments": [
                            {
                                "turn": m.turn,
                                "type": m.moment_type,
                                "description": m.description,
                                "speaker": m.speaker,
                            }
                            for m in result.key_moments
                        ],
                        "turns_completed": result.turns_completed,
                    })

                except Exception as e:
                    print(f"[ERROR] Vib failed: {e}")
                    await ws.send_json({
                        "type": "error",
                        "message": f"Vib conversation failed: {str(e)}",
                    })

            elif msg_type == "list_vibs":
                name = msg.get("name", "").strip()
                soul_id = _storage.get_soul_id_by_name(name) if name else None
                vibs = _storage.list_vibs(soul_id)
                await ws.send_json({
                    "type": "vib_list",
                    "vibs": vibs,
                })

            elif msg_type == "get_vib_result":
                vib_id = msg.get("vib_id")
                if vib_id:
                    result = _storage.load_vib_result(vib_id)
                    transcript = _storage.load_vib_transcript(vib_id)
                    await ws.send_json({
                        "type": "vib_result_loaded",
                        "vib_id": vib_id,
                        "result": result,
                        "transcript": transcript,
                    })
                else:
                    await ws.send_json({
                        "type": "error",
                        "message": "Missing vib_id.",
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
            # WORLD — The Living World
            # ─────────────────────────────────────

            elif msg_type == "send_vib_out":
                # Send a single user's vib into the world to find matches
                soul_name = msg.get("name", "").strip()
                if not soul_name:
                    await ws.send_json({
                        "type": "error",
                        "message": "Need a soul name to send into the world.",
                    })
                    continue

                soul_id = _storage.get_soul_id_by_name(soul_name)
                if not soul_id:
                    await ws.send_json({
                        "type": "error",
                        "message": f"Soul '{soul_name}' not found.",
                    })
                    continue

                if not llm_client:
                    llm_client = _create_llm_client()
                if not llm_client:
                    await ws.send_json({
                        "type": "error",
                        "message": "World requires an LLM connection. Is Ollama running?",
                    })
                    continue

                world = WorldOrchestrator(
                    storage=_storage,
                    llm_client=llm_client,
                )

                await ws.send_json({
                    "type": "world_started",
                    "soul_name": soul_name,
                    "message": f"{soul_name}'s vib is heading out into the world...",
                })

                # Activity callback — what the user sees their vib doing
                async def on_activity(data):
                    await ws.send_json({
                        "type": "vib_activity",
                        "soul_id": data["soul_id"],
                        "soul_name": data["soul_name"],
                        "location": data["location"],
                        "activity": data["activity"],
                        "time": data["time"],
                    })

                # Match callback — the vib found someone
                async def on_match(report):
                    await ws.send_json({
                        "type": "match_found",
                        "your_name": report.your_soul_name,
                        "their_name": report.their_soul_name,
                        "compatibility_score": report.compatibility_score,
                        "where_you_met": report.where_you_met,
                        "how_it_felt": report.how_it_felt,
                        "what_clicked": report.what_clicked,
                        "what_to_watch": report.what_to_watch,
                        "deception_signals": [
                            {
                                "dimension": s.dimension,
                                "what_they_said": s.what_they_said,
                                "what_behavior_shows": s.what_behavior_shows,
                                "confidence": s.confidence,
                                "severity": s.severity,
                            }
                            for s in report.deception_signals
                        ],
                        "their_vibe": report.their_vibe,
                        "conversation_highlights": report.conversation_highlights,
                        "recommendation": report.recommendation,
                        "vib_id": report.vib_id,
                    })

                try:
                    from world.spatial.types import SpatialConfig

                    async def on_spatial_encounter(data):
                        await ws.send_json({
                            "type": "vib_encounter",
                            "soul_a": data.get("soul_a", ""),
                            "soul_b": data.get("soul_b", ""),
                            "location": data.get("location", ""),
                        })

                    # All ready souls enter the world (need 2+ for encounters)
                    # Activity/match callbacks only fire for the requesting user
                    reports = await world.run_day_spatial(
                        soul_ids=None,  # all ready souls
                        on_activity=on_activity,
                        on_encounter=on_spatial_encounter,
                        on_match=on_match,
                        spatial_config=SpatialConfig(bluetooth_range=50.0),
                    )

                    await ws.send_json({
                        "type": "world_complete",
                        "soul_name": soul_name,
                        "matches_found": len(reports),
                        "world_stats": world.get_state_summary(),
                    })

                except Exception as e:
                    print(f"[ERROR] World simulation failed: {e}")
                    import traceback
                    traceback.print_exc()
                    await ws.send_json({
                        "type": "error",
                        "message": f"World simulation failed: {str(e)}",
                    })

            elif msg_type == "run_world_day":
                # Run a full day simulation for all ready souls
                if not llm_client:
                    llm_client = _create_llm_client()
                if not llm_client:
                    await ws.send_json({
                        "type": "error",
                        "message": "World requires an LLM connection.",
                    })
                    continue

                world = WorldOrchestrator(
                    storage=_storage,
                    llm_client=llm_client,
                )

                await ws.send_json({
                    "type": "world_day_started",
                    "message": "A new day begins in the world...",
                })

                async def on_day_activity(data):
                    await ws.send_json({
                        "type": "vib_activity",
                        "soul_id": data["soul_id"],
                        "soul_name": data["soul_name"],
                        "location": data["location"],
                        "activity": data["activity"],
                        "time": data["time"],
                    })

                async def on_day_match(report):
                    await ws.send_json({
                        "type": "match_found",
                        "your_name": report.your_soul_name,
                        "their_name": report.their_soul_name,
                        "compatibility_score": report.compatibility_score,
                        "where_you_met": report.where_you_met,
                        "how_it_felt": report.how_it_felt,
                        "what_clicked": report.what_clicked,
                        "what_to_watch": report.what_to_watch,
                        "deception_signals": [
                            {
                                "dimension": s.dimension,
                                "what_they_said": s.what_they_said,
                                "what_behavior_shows": s.what_behavior_shows,
                                "confidence": s.confidence,
                                "severity": s.severity,
                            }
                            for s in report.deception_signals
                        ],
                        "their_vibe": report.their_vibe,
                        "conversation_highlights": report.conversation_highlights,
                        "recommendation": report.recommendation,
                        "vib_id": report.vib_id,
                    })

                try:
                    from world.spatial.types import SpatialConfig

                    async def on_day_encounter(data):
                        await ws.send_json({
                            "type": "vib_encounter",
                            "soul_a": data.get("soul_a", ""),
                            "soul_b": data.get("soul_b", ""),
                            "location": data.get("location", ""),
                        })

                    reports = await world.run_day_spatial(
                        on_activity=on_day_activity,
                        on_encounter=on_day_encounter,
                        on_match=on_day_match,
                        spatial_config=SpatialConfig(bluetooth_range=50.0),
                    )

                    await ws.send_json({
                        "type": "world_day_complete",
                        "matches_found": len(reports),
                        "world_stats": world.get_state_summary(),
                    })
                except Exception as e:
                    print(f"[ERROR] World day failed: {e}")
                    import traceback
                    traceback.print_exc()
                    await ws.send_json({
                        "type": "error",
                        "message": f"World day failed: {str(e)}",
                    })

            elif msg_type == "get_world_status":
                # Get the current world state
                soul_name = msg.get("name", "").strip()
                soul_id = _storage.get_soul_id_by_name(soul_name) if soul_name else None

                # Count ready souls
                from world.encounter import check_soul_readiness, get_confidence_average
                rows = _storage.db.execute("SELECT id, name FROM souls").fetchall()
                ready_souls = []
                for r in rows:
                    soul_data = _storage.load_soul(r[1])
                    if soul_data:
                        cart = soul_data["cartographer"]
                        avg_conf = get_confidence_average(cart)
                        if check_soul_readiness(soul_data["evidence_count"], avg_conf):
                            ready_souls.append({
                                "name": r[1],
                                "evidence_count": soul_data["evidence_count"],
                                "confidence": round(avg_conf, 2),
                            })

                # Get match history for this soul
                match_history = []
                if soul_id:
                    vibs = _storage.list_vibs(soul_id)
                    for v in vibs:
                        result = _storage.load_vib_result(v["vib_id"])
                        if result:
                            match_history.append({
                                "vib_id": v["vib_id"],
                                "other_soul": (
                                    v["soul_b"] if v["soul_a"] == soul_name
                                    else v["soul_a"]
                                ),
                                "score": result["compatibility_score"],
                                "recommendation": result["recommendation"],
                            })

                await ws.send_json({
                    "type": "world_status",
                    "ready_souls": ready_souls,
                    "total_souls": len(rows),
                    "match_history": match_history,
                })

    except WebSocketDisconnect:
        pass
    finally:
        if llm_client:
            await llm_client.close()
