"""Praxis web app — run a REAL engagement in the browser, with your own answers (not a
simulated persona). You type as the business owner; the same Discovery + firm + deliverable
pipeline runs on the local model; the plan is shown and saved to its own engagement folder.

Run:  .venv\\Scripts\\uvicorn praxis.webapp:app --port 8000
Then open http://localhost:8000

All LLM work is the local Ollama; this server just wires the browser to the pipeline.
"""
import datetime
import re
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from praxis.llm_client import OllamaClient
from praxis.session import DiscoverySession, OPENING
from praxis.pipeline import finalize, save_engagement
from praxis.render import to_markdown

app = FastAPI(title="Praxis")

_INDEX = Path(__file__).parent / "web" / "index.html"


@app.get("/")
async def index():
    return HTMLResponse(_INDEX.read_text(encoding="utf-8"))


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "_", (name or "engagement").lower()).strip("_")
    return s or "engagement"


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    client = OllamaClient()
    session = None
    business = "engagement"
    try:
        while True:
            data = await sock.receive_json()
            kind = data.get("type")

            if kind == "start":
                business = data.get("name") or "engagement"
                # A live human answers, but the firm still sits in on the interview.
                session = DiscoverySession(client, live_firm=True)
                await sock.send_json({"type": "bot", "text": session.opening_line()})

            elif kind == "msg" and session is not None:
                reply = await session.submit(data.get("text", ""))
                if session.is_intake_complete():
                    # Interview done -> run the firm, synthesize, save, and hand back the plan.
                    await sock.send_json({"type": "status",
                                          "text": "Thanks — mapping your workflow and building the plan. "
                                                  "This runs the whole firm on the local model, so give it a minute…"})
                    state = await finalize(client, session.model, session.firm,
                                           session.history, business)
                    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    out = f"engagements/{_slug(business)}_{stamp}"
                    save_engagement(state, out)
                    await sock.send_json({"type": "deliverable",
                                          "markdown": to_markdown(state.deliverable, business),
                                          "saved": out})
                else:
                    await sock.send_json({"type": "bot", "text": reply})
    except WebSocketDisconnect:
        pass
    finally:
        await client.close()
