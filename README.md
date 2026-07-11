# Praxis

**An offline AI-implementation consultancy that runs on your own machine.**

Praxis interviews a business about how it actually works, then hands back a decision-ready plan
for exactly where AI can help — grounded in the owner's own words, for *any* profession, with
every model call running on a local LLM. Nothing leaves the machine.

Made by **[Kardashev Systems](#about)**.

---

## Why it exists

Most "AI for your business" tooling is a cloud service that pattern-matches you into a template.
Praxis is the opposite: a swarm of agents that sit with *your* business, map *your* real
workflow, and reason about *your* actual work — the culling, the drafting, the diagnosing, not
just the paperwork. It is **strictly offline** (a local model, no API keys, no data leaving your
computer) and **fire-and-forget** (hand it the intake, get back a plan).

Two governing principles run through the whole system:

- **The Ocean Principle** — *we are the ocean, the business is the boat.* We adapt to how they
  work; they never adapt to us. No canned templates; the workflow model is an emergent
  evidence-graph built from what the owner actually said.
- **Owned judgment** — the language model extracts and phrases, but it does **not** decide.
  Whether a pain is real, how much it costs, whether an opportunity is worth building — those are
  *measured* from the owner's own words in deterministic, testable code, not left to the model's
  opinion.

## How it works

Praxis is built in two sub-projects. **SP1 (the Diagnostic Firm) is built and working;** SP2
(the Build Wing) is designed and spec'd but not yet implemented.

### SP1 — The Diagnostic Firm

```
  Intake  ─────────────►  Discovery  ─────────►  The Firm  ─────────►  Deliverable
  interview / documents    evidence-graph         five agents           the plan +
  / photos (OCR) / audio   of the workflow        reason & build        SP2 build-handoff
```

1. **Intake** — a live interview *and/or* ingested materials: documents (`.pdf/.docx/.txt`),
   photos of forms and tickets (OCR via RapidOCR), and recordings (transcription via WhisperX).
   Ingested materials *seed* Discovery, which then interviews the owner only about the gaps.
2. **Discovery** — maps the whole job into an evidence-grounded graph (steps, actors, tools,
   artifacts, friction), forcing coverage of the **core value work**, not just the back office.
3. **The Firm** — five persistent agents, each a character with a growing memory who *studies*
   the interview, *morphs* into a stance for this specific business, and *deliberates* to
   determine the product:
   - **Dana** (principal) · **Rubeni** (analyst) · **Sol** (architect) · **Marisol**
     (business-case) · **Idris** (skeptic)
   - They **learn across engagements** — after each business they distill durable lessons into a
     mind that persists to disk and compounds.
4. **Deliverable** — a plain-language plan the owner can act on, plus a machine-readable
   `build_handoff.json` (buildable intervention specs + real data fixtures) for SP2.

### SP2 — The Build Wing *(roadmap)*

Compiles SP1's interventions into runnable automation under the **Airlock Principle**: it
generates and sandbox-verifies artifacts, but never touches production systems — a human crosses
the airlock to deploy. Designed and specified in `docs/superpowers/specs/`, not yet built.

## Quick start

You need [Ollama](https://ollama.com) (the local model server) and Python 3.12.

```bash
# 1. the local model
ollama pull qwen3.5:9b

# 2. dependencies
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # (or .venv/bin/pip on macOS/Linux)

# 3. check your setup, then run
.venv/Scripts/python -m praxis.serve --check
.venv/Scripts/python -m praxis.serve
```

That opens the browser interface. Type a business name, optionally attach documents/photos/audio,
answer the interview, and read the plan. Every run is saved to `engagements/<name>_<timestamp>/`.

**Share it / use it from another device:**

```bash
.venv/Scripts/python -m praxis.serve --tunnel   # public https URL via a Cloudflare tunnel
```

The interview and the firm still run on *your* local model; only the web traffic tunnels.

See **[TESTING.md](TESTING.md)** for the full walkthrough.

## What's in the box

```
praxis/
  session.py         Discovery interview loop (owned completeness, core-work probe)
  discovery.py       extraction: owner's words -> evidence-graph deltas
  analyst.py         find AI opportunities; measured grounding + burden priority
  architect.py       design buildable interventions (trigger/IO/success-criteria)
  business_case.py   score effort / time-saved / risk
  skeptic.py         the quality gate — grounded rejections only
  principal.py       assemble + synthesize the owner-facing plan
  firm.py            the conductor / blackboard
  firm_agent.py      the five agents: memory, morph, learning minds
  grounding.py       OWNED judgment — measure grounding & burden from the owner's words
  ingest.py          documents / images (OCR) / audio (WhisperX)
  webapp.py          browser GUI  ·  serve.py  one-command launcher  ·  preflight.py  checks
tests/praxis/        155+ hermetic tests (no model required)
docs/superpowers/    the SP1 & SP2 design specs
```

## Status & honesty

- **Works well:** discovery on any profession, operational/clerical automation, the
  augmentation layer of core work, deterministic (repeatable) judgment, durable agent memory.
- **The honest frontier:** designing *shippable* interventions for the purest creative
  generation (e.g. generating finished artwork) — Praxis finds and prioritizes it, and surfaces
  it as the top opportunity, but can't always design the specific tool for it on a local model.
- **Not built yet:** SP2 (the automation Build Wing).

Run the test suite:

```bash
.venv/Scripts/python -m pytest tests/praxis/ -q
```

## Tech

Python · FastAPI/uvicorn · local Ollama (default `qwen3.5:9b`, override with `PRAXIS_MODEL`) ·
RapidOCR (images) · WhisperX (audio, optional) · vanilla-JS frontend. No cloud, no API keys.

## License

[MIT](LICENSE) © Kardashev Systems.

## About

**Praxis is made by Kardashev Systems.** The premise is open by design: an AI agency that finds
the holes AI can fill in any business — and gives them the fix — belongs in the open, running on
hardware the business owns.

Contributions welcome. Open an issue or a pull request.
