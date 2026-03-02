# Vib — Agentic Dating

An AI that becomes you. It learns how you think, talk, and feel through natural conversation — then represents you in the dating world as your digital twin.

## Quick Start

### 1. Install Ollama and pull the model

```bash
# Install Ollama: https://ollama.com
ollama pull qwen3.5:4b
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
# Start the web app
uvicorn server:app --port 8000

# Open http://localhost:8000
```

### Using a different model size

```bash
# Use a larger model for better quality (needs more VRAM)
VIB_MODEL=qwen3.5:27b uvicorn server:app --port 8000

# Use the smallest model for testing
VIB_MODEL=qwen3.5:0.8b uvicorn server:app --port 8000
```

## How It Works

### The Interview

The Soul gets to know you through natural conversation. Behind the scenes, three systems work together:

- **Conversation Graph** — tracks emotional temperature, energy, open threads, trust
- **Soul Cartographer** — silently maps personality dimensions from every message
- **Move Generator** — selects conversational moves (open door, follow thread, observation, hypothetical, gentle contradiction, callback, share, rest)

### The Digital Twin

Once enough data is collected, you can "Meet Your Soul" — a self-aware digital twin that speaks as you. It mirrors your communication style, values, emotional patterns, and even your contradictions.

### The Vision

Your Soul talks to other Souls. Compatibility isn't a score — it emerges from whether your digital twins actually have good conversations together.

## Terminal Mode

```bash
# Interactive terminal demo (no web UI)
python demo.py --name "YourName"

# With debug mode
python demo.py --name "YourName" --debug

# Offline (no LLM, shows move selection only)
python demo.py --no-api
```

## Architecture

```
server.py                      <- FastAPI + WebSocket server
interviewer/
├── models.py                  <- State objects (Graph, Cartographer, Move types)
├── move_generator.py          <- Decision engine (eligibility -> scoring -> selection)
├── prompt_builder.py          <- LLM prompt assembly
├── orchestrator.py            <- Main loop (analyze -> update -> select -> generate)
├── llm_client.py              <- Ollama client with model routing
└── persona_builder.py         <- Compiles digital twin persona from Cartographer data
static/
├── index.html                 <- Chat UI
├── style.css                  <- Dark, intimate aesthetic
└── app.js                     <- WebSocket client + UI logic
```

## Tests

```bash
pytest -v
```
