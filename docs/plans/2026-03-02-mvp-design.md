# Vib MVP Design — The Soul with Digital Twin

**Date:** 2026-03-02
**Status:** Approved
**Goal:** Investor-demoable MVP running on local Qwen 3.5 via Ollama

## The Product Vision

The Soul interviews a user through natural conversation, silently building a deep personality model. Once enough data is collected, the user can "meet their Soul" — a self-aware digital twin that speaks as them, mirrors their communication style, values, and emotional patterns. The twin knows it's a Soul but genuinely represents how the user thinks and feels.

This is the foundation of agentic dating: your Soul talks to other Souls autonomously, and compatibility emerges from whether the digital twins actually vibe — not from a checklist.

## MVP Scope

### In Scope
- Ollama + Qwen 3.5 local LLM backend (replaces Anthropic API)
- FastAPI + WebSocket server
- Vanilla HTML/CSS/JS chat frontend (dark, intimate aesthetic)
- Interview mode: existing 3-system architecture (Graph, Cartographer, Move Generator)
- Soul Mirror mode: talk to your own digital twin
- Soul Persona Builder: compiles Cartographer state into a generative replica prompt

### Out of Scope
- User accounts / auth
- Database / persistence (ephemeral sessions)
- Agent-to-agent matching / negotiation
- Deployment config (Docker, CI/CD)
- Mobile optimization
- Debug mode in web UI

## Architecture

```
Browser (vanilla JS)
  |
  +-- WebSocket --> FastAPI Server (server.py)
                      |
                      +-- InterviewerSession (orchestrator.py)
                      |     +-- ConversationGraph     (System 1)
                      |     +-- CartographerState      (System 2)
                      |     +-- MoveGenerator          (System 3)
                      |
                      +-- SoulMirrorSession (new)
                      |     +-- PersonaBuilder
                      |     +-- CartographerState (read-only snapshot)
                      |
                      +-- OllamaLLMClient (llm_client.py, rewritten)
                            |
                            +-- HTTP --> Ollama (localhost:11434)
                                           +-- qwen3.5
```

## Component Details

### 1. LLM Client (llm_client.py — rewritten)

Async HTTP client using `httpx` talking to Ollama at `localhost:11434/api/chat`.

Model routing:
- **Interviewer** (conversation): qwen3.5, temperature 0.75, max_tokens 512
- **Cartographer** (JSON analysis): qwen3.5, temperature 0.3, max_tokens 1024, format: "json"
- **Soul Mirror** (twin generation): qwen3.5, temperature 0.8, max_tokens 512

Cartographer JSON fallback chain:
1. Parse response as JSON directly
2. Extract JSON from markdown code blocks
3. Regex extraction of key fields
4. Return safe default dict

### 2. FastAPI Server (server.py)

Endpoints:
- `GET /` — serves static frontend
- `WebSocket /ws` — main chat connection

WebSocket protocol:
```json
// Start interview
{"type": "start", "name": "Alex"}
-> {"type": "opening", "text": "Hey Alex..."}

// Send message (interview mode)
{"type": "message", "text": "I just moved to a new city"}
-> {"type": "response", "text": "...", "move": "follow_thread", "phase": "first_contact"}

// Request soul readiness
{"type": "command", "command": "status"}
-> {"type": "status", "data": {...}}

// Switch to Soul Mirror mode
{"type": "command", "command": "mirror"}
-> {"type": "mode_change", "mode": "mirror", "text": "Hey... I'm your Soul."}

// Send message (mirror mode)
{"type": "message", "text": "What do you think about long distance?"}
-> {"type": "response", "text": "Honestly? I'd try it but...", "mode": "mirror"}
```

Each WebSocket connection gets its own session. Ephemeral — dies on disconnect.

### 3. Soul Persona Builder (interviewer/persona_builder.py — new)

Takes CartographerState + conversation history and compiles a system prompt for the digital twin.

The prompt includes:
- **Communication style**: long/short responses, humor type, vocabulary, formality
- **Core values**: demonstrated priorities from interview data
- **Emotional patterns**: what energizes them, what they avoid, vulnerability comfort
- **Relationship orientation**: attachment style, conflict style, independence level
- **Contradictions**: stated vs demonstrated gaps (makes the twin feel real, not idealized)
- **Speech patterns**: specific phrases, sentence structure, rhythm

The twin speaks in first person ("I think...", "I'd probably...") but is self-aware — if asked what it is, it acknowledges being a Soul honestly.

### 4. Frontend (static/)

Single-page chat UI:
- Dark background, centered chat container (max-width ~600px)
- Top: "Vib" branding, "Meet Your Soul" button (enabled after confidence threshold)
- Middle: scrolling messages — Soul in soft purple (left), user in soft blue (right)
- Bottom: text input + send
- Name entry screen on first load
- Status overlay showing dimension confidence bars on demand
- Mode indicator when in Soul Mirror mode

Aesthetic: intimate, warm, slightly moody. iMessage-meets-therapy-app.

No framework — vanilla HTML/CSS/JS with native WebSocket API.

### 5. Package Structure

```
Vib - Agentic Dating/
+-- server.py                  <- FastAPI entry point
+-- requirements.txt           <- fastapi, uvicorn, httpx, websockets
+-- README.md                  <- Updated setup/run instructions
+-- demo.py                    <- Kept for terminal mode (updated imports)
+-- interviewer/
|   +-- __init__.py
|   +-- models.py              <- Moved from root, unchanged
|   +-- move_generator.py      <- Moved, imports fixed
|   +-- prompt_builder.py      <- Moved, imports fixed
|   +-- orchestrator.py        <- Moved, made async, imports fixed
|   +-- llm_client.py          <- Rewritten for Ollama (async)
|   +-- persona_builder.py     <- New: compiles twin persona prompt
+-- static/
    +-- index.html
    +-- style.css
    +-- app.js
```

### 6. What Changes in Existing Code

- **models.py**: No changes to data structures
- **move_generator.py**: No logic changes, only import paths
- **prompt_builder.py**: No logic changes, only import paths
- **orchestrator.py**: `process_turn` becomes async (awaits LLM calls), import paths fixed, new `get_persona_snapshot()` method added for persona builder
- **llm_client.py**: Full rewrite — Anthropic SDK replaced with httpx calls to Ollama
- **demo.py**: Import paths updated, kept as alternative terminal interface

## The Investor Demo Flow

1. Investor opens the web app in a browser
2. Enters their name, starts chatting with The Soul
3. The Soul runs through its interview — open doors, follow threads, observations, hypotheticals
4. After 10-15 exchanges, the "Meet Your Soul" button lights up
5. They click it and start talking to their own digital twin
6. The twin responds in their style, with their values, carrying their contradictions
7. That's the pitch: "Now imagine your Soul meeting other Souls. That's the dating."
