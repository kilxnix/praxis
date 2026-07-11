# Testing Praxis

Praxis interviews a business about how it works and hands back a decision-ready plan for where
AI can help — running entirely on a local model, nothing leaves the machine.

## What you need (one-time)

1. **Ollama** — the local model server. Install from https://ollama.com and let it run.
2. **The model** — in a terminal:
   ```
   ollama pull qwen3.5:9b
   ```
   (Or set `PRAXIS_MODEL` to a model you already have.)
3. **Python 3.12** with the dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
   Audio ingest is optional and heavy — only if you want to feed recordings:
   ```
   .venv\Scripts\pip install whisperx
   ```

## Check your setup

```
.venv\Scripts\python -m praxis.serve --check
```
Every line marked `[OK ]` is ready; `[XX]` is a required problem (with the fix shown); `[--]` is
an optional ingest format you can skip.

## Run it

**Windows:** double-click `start-praxis.bat`.

**Any OS:**
```
.venv\Scripts\python -m praxis.serve
```
It preflights, starts the app, and opens http://localhost:8000 in your browser.

## Test the pipeline

1. Type a **business name** (e.g. "Maria's HVAC").
2. Optionally **attach materials** — a document, a photo of a form/ticket (it's OCR'd), or a
   recording (WhisperX). Praxis reads them first, then interviews you only about the gaps.
3. **Answer the interview** in your own words, as the business owner. Give real details when
   asked (a real part number, a typical job) — those become the ground truth the plan is built
   on. It takes a few minutes on a local model.
4. When it's mapped the whole job it runs the firm and shows the **plan** in the page.

Every run is saved to its own folder:
```
engagements/<business>_<timestamp>/
  deliverable.md      the plan the owner reads
  engagement.json     the full record (map, transcript, every agent hand-off)
  build_handoff.json  the buildable spec + fixtures (what SP2 would compile)
  firm/<employee>.md  each of the five employees: who they became, understood, learned
```

## Notes

- **Fully offline / no tokens.** All model work is your local Ollama; run it as much as you like.
- **A run takes a few minutes** and uses your CPU/GPU heavily — that's the local model thinking.
- **"Start another engagement"** resets for the next business. The firm's five employees keep
  what they learned across runs (`firm_minds/`), so they arrive at the next business seasoned.
- If a run seems stuck, the model is just slow; give it a minute before assuming a problem.
