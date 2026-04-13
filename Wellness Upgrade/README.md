# Vib

A wellness companion. You log meals, mood, and how you touched the day;
Vib tracks the overlap and makes small, specific suggestions. Quiet by
default. Doesn't moralize food. Doesn't break streaks.

This is a pivot of the existing Vib codebase (an agentic dating app)
into a wellness companion. The Soul Cartographer / Move Generator /
Conversation Graph spine carries over directly. Two packages get
deleted, the personality dimensions get swapped for wellness state
dimensions, and logging + vision + nudges + a post-binge protocol
get added on top.

**The full pivot plan is in `wellness-pivot-plan.md`. Read it first.**

## Stack (existing)

- **Python / FastAPI / Uvicorn** — backend
- **Ollama** with `qwen3.5:9b` — all conversational inference, local
- **SQLite (WAL mode)** — persistence via `interviewer/storage.py`
- **Vanilla JS frontend, PWA-ready** — WebSocket-based
- **pytest + pytest-asyncio** — test suite

## Stack (additions for the wellness pivot)

- **`qwen2.5-vl:7b`** in Ollama — for parsing food photos. Same family
  as the chat model, runs locally, keeps the privacy story intact.
- **`python-multipart` + `Pillow`** — for photo upload + preprocessing.
- New `vib_wellness/` package — logging, vision, nudges, post-binge
  middleware, insights, store cache, receipt parsing.

That's it. No new languages, no new databases, no new infra. The pivot
is mostly delete + rename + extend.

## What carries over from dating Vib

- The entire `interviewer/` package — Conversation Graph, Cartographer,
  Move Generator, Prompt Builder, LLM Client, Persona Builder, Storage.
  This is the spine.
- The 4-phase model (renamed: ARRIVAL → DAILY_RHYTHM → ATTUNED → COMPANION).
- The trust score (renamed `attunement_confidence`).
- The emotional temperature, open threads, energy tracking — all of it.
- The 8-move generator pipeline (with eligibility → emotional override
  → weighted scoring), with the move set lightly remapped and 2 new
  moves added.
- The `trait_evidence` table — same structure, new dimension names.
- The `contradictions` table — this becomes the gentle pattern-callback
  mechanic for the weekly insights view. Surfacing "you said X, you do Y"
  with high trust is *exactly* the indirect-confrontation pattern Vib
  needs for things like noticing weekend binge clusters.
- `llm_client.py`'s model routing tiers — already model-agnostic, just
  add a `vision` tier alongside interviewer/cartographer/mirror.
- The persona_builder's speech-pattern analysis — repurposed: instead
  of building a digital twin sent into the world, it builds the
  user's voice profile so Vib can match their tone.
- FastAPI WebSocket protocol shape, soul lookup by name, full
  conversation persistence — all of it, as-is.

## What gets deleted

- `vib/` package (the soul-to-soul conversation engine).
- `world/` package (locations, encounters, routine, spatial).
- Tests for both.
- WebSocket handlers for `start_vib`, `send_vib_out`, `run_world_day`.
- Frontend screens for the world view and match reports.

## What gets added

- New tables: `entries` (polymorphic log), `vib_state`, `risk_windows`,
  `nudges`, `store_items`, `shortcuts`. Migrations in
  `migrations/001_add_wellness_tables.sql`.
- `vib_wellness/` package: logging service, vision service, nudge cron,
  post-binge middleware, insights service, state computer, store cache,
  receipt parser (port from your Base44 work).
- New WebSocket message types: `log_meal`, `log_mood`, `log_sleep`,
  `log_walk`, `log_binge`, `tag_meal_as_binge`, `request_state`,
  `request_insights`, etc. Server-side: `entry_logged`, `state_update`,
  `nudge`, `insight`, `post_binge_mode_change`.
- `POST /upload/photo` HTTP endpoint for photo logging.
- New frontend screens: home dashboard, logging modal, insights view.

## Founding design principles (non-negotiable)

1. **No moralizing.** No green/red. No good/bad days. No streaks.
   No compensating math.
2. **Heavy days get gentler responses, not stricter.** Hardcoded in
   the post-binge middleware. See `vib-layer.md` § Post-binge protocol.
3. **Suggestions have a destination.** Never "eat more protein." Always
   "want to walk to the Circle K — it's about 8 minutes — and grab a
   couple Fairlifes?"
4. **Mood is logged before food.** A `state_check` move triggers when
   the user is about to log a meal and there's no recent mood entry.
5. **Vib has a name and a consistent voice.** Same character throughout.
6. **Privacy is the moat.** Everything runs on local Ollama. The
   "your binges never leave your phone" promise is real and enforced
   by the architecture.
7. **Quietness is the default.** Nudges happen at most twice a day,
   only when Vib has something specific to say.

## Files in this kit

- `README.md` — this file.
- `wellness-pivot-plan.md` — **the master plan.** File-by-file changes,
  concept mapping, dimension remap, move remap, vision routing,
  post-binge middleware, SQLite migrations, frontend changes,
  4-week execution order. This is the document you work from.
- `v1-spec.md` — the product spec (screens, daily loop, what ships in v1).
- `vib-layer.md` — domain-level spec for the attunement layer + the
  hardcoded post-binge protocol. Stack-agnostic, still correct after
  the pivot.
- `prompts/vib-system-prompt.md` — Vib's voice and rules. Drops into
  `prompt_builder.py` as the new base persona.

## Run it (after the pivot)

```bash
ollama serve
ollama pull qwen3.5:9b
ollama pull qwen2.5-vl:7b
pip install -r requirements.txt
python -c "import sqlite3; sqlite3.connect('vib.db').executescript(open('migrations/001_add_wellness_tables.sql').read())"
uvicorn server:app --port 8000
# PWA at localhost:8000
pytest tests/ -v
```

## The eventual hardware play (held loosely)

If wellness Vib is loved by enough people, the natural extension is a
small wearable or pendant that witnesses the day passively (steps,
ambient light, voice journaling) and syncs to the sidekick. Don't build
it. Don't talk about it publicly. Hold it as a direction the company
*could* go, not a roadmap promise. v1 ships as a PWA.

## The honest commercial path

Free PWA for v1. $5/mo "support development" tier later. No paywall
on core features. After 6 months, if there are real users who love it,
$8/mo for new sign-ups, original supporters grandfathered. This product
grows on word of mouth from people who recognize the design as
different. It does not grow on paid acquisition or VC pressure.
