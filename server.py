"""
Vib — FastAPI Server

WebSocket-based chat server for The Soul interviewer and Soul Mirror.
Serves the static frontend and manages per-connection interview sessions.

Run: uvicorn server:app --reload
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from interviewer.orchestrator import InterviewerSession
from interviewer.llm_client import OllamaLLMClient
from interviewer.persona_builder import build_soul_persona
from interviewer.prompt_builder import BASE_SYSTEM_PROMPT, PHASE_PROMPTS, MOVE_STYLE_GUIDES
from interviewer.models import Phase, MoveType

app = FastAPI(title="Vib — The Soul")

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


def _create_llm_client():
    """Create an Ollama client. Returns None if Ollama isn't reachable or the model is missing."""
    import httpx
    from interviewer.llm_client import ModelTier

    try:
        # Verify Ollama is reachable and the required model is available
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        resp.raise_for_status()
        data = resp.json()
        available = {m["name"].split(":")[0] for m in data.get("models", [])}
        # Also include full name:tag entries
        available.update(m["name"] for m in data.get("models", []))
        required_model = ModelTier.INTERVIEWER
        # Check both exact match and base name match
        if required_model not in available and required_model.split(":")[0] not in available:
            return None
        return OllamaLLMClient()
    except Exception:
        return None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    session = None
    llm_client = None
    mirror_mode = False
    mirror_history = []

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start":
                name = msg.get("name", "friend").strip() or "friend"
                llm_client = _create_llm_client()
                session = InterviewerSession(user_name=name, llm_client=llm_client)
                mirror_mode = False
                mirror_history = []

                opening = f"Hey {name}. I'm glad you're here. What's been on your mind?"
                if llm_client:
                    try:
                        opening_system = (
                            BASE_SYSTEM_PROMPT + "\n\n"
                            + PHASE_PROMPTS[Phase.FIRST_CONTACT] + "\n\n"
                            + MOVE_STYLE_GUIDES[MoveType.OPEN_DOOR] + "\n\n"
                            + f"The user's name is {name}. This is your very first interaction. "
                            + f"Generate a warm, natural opening. Introduce the vibe — you're here "
                            + f"to get to know them. Don't be formal. Don't explain the system. "
                            + f"Just be a presence they want to talk to. 2-3 sentences max."
                        )
                        opening = await llm_client.interviewer_generate(
                            system=opening_system,
                            messages=[{"role": "user", "content": f"[Start conversation with {name}]"}],
                        )
                    except Exception as e:
                        print(f"[LLM ERROR] Opening generation failed: {e}")
                        llm_client = None
                        session.llm_client = None

                session.conversation_history.append({"role": "assistant", "content": opening})
                await ws.send_json({"type": "opening", "text": opening})

            elif msg_type == "message" and session:
                text = msg.get("text", "").strip()
                if not text:
                    continue

                if mirror_mode:
                    mirror_history.append({"role": "user", "content": text})
                    if llm_client:
                        persona_prompt = build_soul_persona(
                            name=session.user_name,
                            cartographer=session.cartographer,
                            conversation_history=session.conversation_history,
                        )
                        response = await llm_client.mirror_generate(
                            system=persona_prompt,
                            messages=mirror_history,
                        )
                    else:
                        response = f"[MIRROR] I'd say... that sounds like something I'd think about."

                    mirror_history.append({"role": "assistant", "content": response})
                    await ws.send_json({
                        "type": "response",
                        "text": response,
                        "mode": "mirror",
                    })
                else:
                    try:
                        result = await session.process_turn(text)
                    except Exception as e:
                        print(f"[LLM ERROR] process_turn failed: {e}")
                        llm_client = None
                        session.llm_client = None
                        result = await session.process_turn(text)
                    await ws.send_json({
                        "type": "response",
                        "text": result["response"],
                        "move": result["move"].move_type.value,
                        "phase": result["phase"].name,
                    })

            elif msg_type == "command" and session:
                command = msg.get("command")

                if command == "status":
                    report = session.get_soul_readiness()
                    await ws.send_json({"type": "status", "data": report})

                elif command == "mirror":
                    mirror_mode = True
                    mirror_history = []

                    if llm_client:
                        persona_prompt = build_soul_persona(
                            name=session.user_name,
                            cartographer=session.cartographer,
                            conversation_history=session.conversation_history,
                        )
                        greeting = await llm_client.mirror_generate(
                            system=persona_prompt,
                            messages=[{"role": "user", "content": "[Someone wants to talk to you. Say hi as yourself.]"}],
                        )
                    else:
                        greeting = f"Hey... so, I'm {session.user_name}'s Soul. This is weird, right? Ask me anything."

                    mirror_history.append({"role": "assistant", "content": greeting})
                    await ws.send_json({
                        "type": "mode_change",
                        "mode": "mirror",
                        "text": greeting,
                    })

                elif command == "interview":
                    mirror_mode = False
                    await ws.send_json({
                        "type": "mode_change",
                        "mode": "interview",
                        "text": "Welcome back. Where were we?",
                    })

    except WebSocketDisconnect:
        pass
    finally:
        if llm_client:
            await llm_client.close()
