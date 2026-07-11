"""Praxis web app — run a REAL engagement in the browser, with your own answers (not a
simulated persona). You type as the business owner; the same Discovery + firm + deliverable
pipeline runs on the local model; the plan is shown and saved to its own engagement folder.

Run:  .venv\\Scripts\\uvicorn praxis.webapp:app --port 8000
Then open http://localhost:8000

All LLM work is the local Ollama; this server just wires the browser to the pipeline.
"""
import datetime
import os
import re
import secrets
import tempfile
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse

from praxis.llm_client import OllamaClient
from praxis.session import DiscoverySession
from praxis.ingest import ingest_files_with_fixtures, SUPPORTED_EXTS
from praxis.pipeline import finalize, save_engagement
from praxis.render import to_markdown

app = FastAPI(title="Praxis")

_INDEX = Path(__file__).parent / "web" / "index.html"


@app.get("/")
async def index():
    return HTMLResponse(_INDEX.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    """Readiness a tester (or the page) can check: is Ollama up, the model pulled, deps present."""
    from praxis.preflight import run_checks
    checks = run_checks()
    return {"ready": all(c.ok for c in checks if c.required),
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail,
                        "fix": c.fix, "required": c.required} for c in checks]}


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "_", (name or "engagement").lower()).strip("_")
    return s or "engagement"


# Seeded-but-not-yet-started sessions, keyed by a token the browser passes to the WS.
_SEEDED = {}


@app.post("/seed")
async def seed(name: str = Form("engagement"), files: list[UploadFile] = File(...)):
    """Ingest real materials (documents / OCR'd photos / recordings) and SEED a discovery
    session with them, so the interview starts already knowing the business and probes only the
    gaps. Ingest increases what discovery starts with — it does not replace the interview.
    Returns a session token + the first (gap-directed) question; the browser then opens the WS."""
    tmp_paths = []
    try:
        for up in files:
            ext = os.path.splitext(up.filename or "")[1].lower()
            if ext not in SUPPORTED_EXTS:
                return JSONResponse({"error": f"unsupported file: {up.filename}"}, status_code=400)
            fd, tp = tempfile.mkstemp(suffix=ext)
            with os.fdopen(fd, "wb") as f:
                f.write(await up.read())
            tmp_paths.append(tp)
        try:
            text, fixtures = ingest_files_with_fixtures(tmp_paths)   # + real samples for SP2
        except RuntimeError as e:               # e.g. WhisperX not installed
            return JSONResponse({"error": str(e)}, status_code=400)
        if not text.strip():
            return JSONResponse({"error": "no readable text found in the uploaded files"}, status_code=400)

        client = OllamaClient()                 # kept open; the WS that adopts this session closes it
        session = DiscoverySession(client, live_firm=True)
        first_q = await session.seed_from_text(text, fixtures=fixtures)
        token = secrets.token_hex(8)
        _SEEDED[token] = (session, name)
        return {"session_id": token, "opening": first_q}
    finally:
        for tp in tmp_paths:
            try:
                os.remove(tp)
            except OSError:
                pass


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    client = None
    session = None
    business = "engagement"
    try:
        while True:
            data = await sock.receive_json()
            kind = data.get("type")

            if kind == "start":
                token = data.get("session_id")
                if token and token in _SEEDED:
                    # Adopt the session seeded from uploaded materials; open with its gap question.
                    session, business = _SEEDED.pop(token)
                    client = session.client
                    await sock.send_json({"type": "bot", "text": session.history[-1]["content"]})
                else:
                    business = data.get("name") or "engagement"
                    client = OllamaClient()
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
                                           session.history, business, fixtures=session.fixtures,
                                           core_steps=session.core_step_labels)
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
        if client is not None:
            await client.close()
