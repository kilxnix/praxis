# The Soul — Interviewer Engine v0.1

An AI agent that gets to know you through natural conversation, building a progressively deeper model of who you are.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Run

```bash
# Full interactive demo with Opus 4.6
python demo.py --name "YourName"

# With debug mode (shows internal state — move selection, trait signals, trust score)
python demo.py --name "YourName" --debug

# Offline mode — see move decisions without API calls
python demo.py --no-api
```

## In-Session Commands

| Command | Action |
|---|---|
| `/status` | View Soul readiness report (dimension confidence, matchability) |
| `/debug` | Toggle debug view (internal state per turn) |
| `/newsession` | Simulate leaving and returning (tests session continuity, callbacks) |
| `quit` | Exit and see final Soul report |

## Architecture

```
demo.py                     ← Interactive terminal UI
interviewer/
├── models.py               ← State objects (Graph, Cartographer, Move types + constraints)
├── move_generator.py       ← Decision engine (eligibility → emotional override → scoring → selection)
├── prompt_builder.py       ← LLM prompt assembly (persona → phase → move style → context)
├── orchestrator.py         ← Main loop (analyze → update → select → generate → validate)
└── llm_client.py           ← Anthropic API wrapper with model routing
```

## The Three Systems

**System 1 — Conversation Graph:** Tracks where you are in the dialogue. Temperature, energy, open threads, trust, phase.

**System 2 — Soul Cartographer:** Silently maps personality dimensions from every message. Tracks confidence levels, stated vs. demonstrated traits, contradictions.

**System 3 — Move Generator:** Selects the right conversational move (Open Door, Follow Thread, Observation, Hypothetical, Gentle Contradiction, Callback, Share, Rest) based on what Systems 1 and 2 report.

## Phases

1. **First Contact** — Light, warm, building rapport. Mostly Open Doors and Follow Threads.
2. **Pattern Recognition** — Observations and Callbacks appear. "You keep coming back to..."
3. **Depth** — Gentle Contradictions unlocked. Attachment, conflict, vulnerability explored.
4. **Ongoing** — Soul is matchable. Agent evolves the model, handles post-date debriefs.
