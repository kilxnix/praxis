# Vib — Wellness Pivot Plan

The complete file-by-file plan for transitioning the existing Vib codebase
(agentic dating app) into Vib (wellness companion). This document is the
single source of truth for the pivot. Hand it to Claude Code or work
through it linearly yourself.

The good news, said up front: ~80% of what you need is already built. The
Interviewer system is, structurally, the wellness attunement layer. You
are mostly renaming, deleting two packages, swapping concept dimensions,
and adding logging + vision + nudges. You are not building from scratch.

---

## Table of contents

1. The pivot in one paragraph
2. Branch and safety
3. File-by-file: DELETE
4. File-by-file: MODIFY
5. File-by-file: ADD
6. Concept mapping (the renames)
7. New Cartographer dimensions (the new "10")
8. New Move Generator (the new 8 + 2 moves)
9. New base persona for prompt_builder
10. Vision routing (the photo → macros path)
11. Post-binge protocol middleware
12. Storage additions (SQLite)
13. WebSocket protocol changes
14. Frontend (static/) changes
15. Execution order — week by week
16. Validation checklist

---

## 1. The pivot in one paragraph

Wellness Vib is the existing Vib codebase with two packages deleted
(`vib/`, `world/`), the Interviewer system's 10 personality dimensions
swapped for 10 wellness state dimensions, the 8 moves lightly remapped
and 2 new moves added, the base persona rewritten from "sharp friend"
to "soft companion who notices," a new polymorphic `entries` table added
to storage for logging meals/mood/walks/etc., a vision-capable model
added to Ollama for parsing food photos, a nudge cron added for
proactive messages, and a hardcoded post-binge protocol middleware that
sits in front of the orchestrator. Same FastAPI server, same WebSocket
protocol shape, same SQLite storage, same PWA frontend — extended, not
replaced.

---

## 2. Branch and safety

```bash
git checkout -b wellness-pivot
git tag pre-pivot-snapshot          # so you can come back to dating Vib if you ever want
```

The dating Vib lives forever on the `pre-pivot-snapshot` tag and on the
old default branch. The wellness work happens on `wellness-pivot` and
becomes the new default once it's working. Don't try to keep both
products alive in the same branch. Cut clean.

---

## 3. File-by-file: DELETE

Delete the entire packages — these don't survive the pivot:

```
vib/                          # soul-to-soul conversation engine
  models.py
  orchestrator.py
  evaluator.py
  prompts.py

world/                        # world simulation, locations, encounters
  models.py
  orchestrator.py
  encounter.py
  routine.py
  locations.py
  reporter.py
  spatial/
    (everything in here)

tests/test_vib_*              # any tests for the deleted packages
tests/test_world_*
```

You will feel resistance to deleting `world/spatial/` because the
3D proximity engine is technically interesting. Delete it anyway. It
does not serve the new product and keeping it around will pull
attention sideways for months.

In `server.py`, delete the WebSocket message handlers for: `start_vib`,
`send_vib_out`, `run_world_day`, `run_world_day_spatial`, `match_found`,
`vib_turn`, `vib_result`. Also delete any imports from `vib/` and
`world/`.

In `static/`, delete: any "world view" screen, any "match report"
screen, any "send your soul out" UI. Keep the entry screen, the
interview chat UI, and the soul panel — those become the foundation
of the new screens.

In `requirements.txt`, you can probably remove `Pillow` if it was only
used by `world/spatial/`. Re-add it later when you wire up the photo
upload path; you'll need it then.

---

## 4. File-by-file: MODIFY

### `interviewer/models.py`

Rename and reshape the core enums and dataclasses:

- `Phase` enum: rename values
  - `FIRST_CONTACT` → `ARRIVAL`
  - `PATTERN_RECOGNITION` → `DAILY_RHYTHM`
  - `DEPTH` → `ATTUNED`
  - `ONGOING` → `COMPANION`
- `MoveType` enum: see § 8 for the new full set.
- `TraitConfidence` → `DimensionConfidence` (rename only; the structure
  is fine).
- `CartographerState`: keep the structure, but the `dimensions` dict now
  holds wellness state dimensions (see § 7), not Big Five + relationship
  traits.
- Add a new field to `CartographerState`: `post_binge_mode: Optional[Literal["acute", "soft_morning"]] = None`.
- Add `post_binge_until: Optional[datetime] = None`.
- `ConversationGraph`: keep as-is. Trust score, emotional temperature,
  open threads, energy — all of these concepts transfer literally. The
  emotional_temperature enum (COLD/COOL/WARM/HOT/VOLATILE) still works,
  it just now reflects the user's wellbeing rather than rapport
  intensity.

### `interviewer/orchestrator.py`

`InterviewerSession.process_turn()` is the right shape, mostly keep it.
Three changes:

1. **Rename** `InterviewerSession` → `VibSession`. (It was already called
   that in `vib/orchestrator.py` which you're deleting, so the name is
   now free.)
2. **Insert post-binge middleware** at the top of `process_turn()` —
   before move generation, check `cartographer_state.post_binge_mode`.
   If set, override the move set and tone sliders before proceeding.
   See § 11.
3. **Insert a logging-side-channel handler.** When the incoming WebSocket
   message is a structured log (`log_meal`, `log_mood`, etc.) instead of
   a chat message, branch to a different code path that writes the entry
   and triggers a *short* acknowledgment from Vib (one move only,
   typically `acknowledge` or `observation`), then returns. Don't run
   the full move generator pipeline for logs — they're high-frequency,
   low-stakes, and the user is in flow.

### `interviewer/move_generator.py`

The pipeline (eligibility → emotional override → weighted scoring →
selection) is *exactly* right and stays. What changes is the move set
itself — see § 8 for the full new set with eligibility rules and
scoring weights.

The "rapport beats data" emotional override gets renamed to
"presence beats progress" and triggers on the same conditions plus
two new ones: `post_binge_mode is not None` and `mood_now == "low" and in_risk_window`.

The thread exhaustion detection (3+ follow_threads in a row → switch up)
stays. It's a great mechanic and applies just as much to wellness
conversations as to interviews.

### `interviewer/prompt_builder.py`

The layered architecture stays. The base persona changes — see § 9 for
the full new base persona text. The phase prompts get rewritten for the
new phases (ARRIVAL/DAILY_RHYTHM/ATTUNED/COMPANION). The move style
guides get rewritten for the new moves. The metadata block expands to
include: current macro state, mood reading, sleep, day-touched trio,
post-binge mode, in-risk-window flag. The hard constraints list is
extended with the wellness-specific banned phrases from
`prompts/vib-system-prompt.md`.

### `interviewer/llm_client.py`

Add a fourth model tier: `vision`. See § 10 for the full routing
addition. The existing `interviewer / cartographer / mirror` tiers
all stay. The default model env var stays as `VIB_MODEL`.

### `interviewer/persona_builder.py`

Repurpose, don't rewrite. Currently it builds two contexts: `mirror`
(talking to the user about themselves) and `vib` (representing the
user to another soul). Delete the `vib` context — there is no other
soul anymore. Keep the `mirror` context and rename it to `companion_voice` — Vib uses this to match the user's tone (length, formality,
hedging, humor) when speaking back. Same code, narrower purpose.

### `interviewer/storage.py`

Keep all existing tables. Add the new tables in § 12. Update the
`CartographerState` load/save to handle the new dimensions and the
`post_binge_mode` field.

The existing `trait_evidence` table stays — wellness Vib uses it
exactly the same way. Each entry the user logs adds rows of evidence
for the relevant wellness dimensions, with confidence and a quote (or
the entry payload as the "quote").

The existing `contradictions` table stays, and this is the gold of the
pivot: the dating Vib's "you said X, you do Y" surfacing mechanic is
*exactly* the gentle pattern-callback mechanic for wellness Vib. "You
said you wanted to eat lighter on weekends; the last three Saturdays
trended heavy." Same table, same surfacing logic, new domain.

### `server.py`

Add the new WebSocket message types (§ 13). Wire each one to its
handler. Delete the dating-app message handlers. The session lifecycle
(create soul → load soul by name → return) stays exactly the same.
Add a new HTTP endpoint `POST /upload/photo` for the photo logging
path (binary upload, returns photo ID, then the WebSocket message
references the ID).

### `static/`

See § 14. The interview chat UI is reused as the conversation surface
with Vib. New screens get added: home dashboard, logging modal, insights
view. Soul panel becomes the wellness state panel.

### `demo.py`

Update the terminal demo to walk through a wellness conversation
instead of an interview. Useful for testing without the frontend.

### `requirements.txt`

Add: `python-multipart` (for photo uploads), `Pillow` (for image
preprocessing before sending to vision model). Keep everything else.

### Tests

Update existing interviewer tests to use the new dimensions and moves.
Add new tests for: logging endpoints, post-binge middleware, vision
routing, nudge scheduler, the dimension evidence accumulation.

---

## 5. File-by-file: ADD

```
vib_wellness/                      # new package — wellness-specific services
  __init__.py
  logging_service.py               # handles log_meal, log_mood, etc.
  vision_service.py                # photo → macros via vision model tier
  nudge_service.py                 # cron-style proactive nudge scheduler
  post_binge.py                    # the protocol middleware
  insights_service.py              # weekly insights generation
  state_computer.py                # computes VibState from entries
  store_cache.py                   # store_items refresh job
  receipt_parser.py                # ported from your Base44 work

migrations/
  001_add_wellness_tables.sql      # the SQLite migrations from § 12

static/
  home.html                        # new home dashboard
  log.html                         # new logging modal (or a JS overlay)
  insights.html                    # new insights view
  styles/
    vib.css                        # restyled, soft, low-pressure aesthetic

prompts/
  base_persona_companion.txt       # the new base persona text (§ 9)
  phase_arrival.txt
  phase_daily_rhythm.txt
  phase_attuned.txt
  phase_companion.txt
  move_*.txt                       # one per move (§ 8)
```

---

## 6. Concept mapping (the renames)

| Old (dating Vib) | New (wellness Vib) | Notes |
|---|---|---|
| `Phase.FIRST_CONTACT` | `Phase.ARRIVAL` | First few sessions; Vib is learning who you are |
| `Phase.PATTERN_RECOGNITION` | `Phase.DAILY_RHYTHM` | Vib has enough data to spot patterns |
| `Phase.DEPTH` | `Phase.ATTUNED` | Trust is high enough for gentle pattern callbacks |
| `Phase.ONGOING` | `Phase.COMPANION` | Long-term steady state |
| `trust_score` | `attunement_confidence` | Same field, more accurate name |
| `emotional_temperature` | `state_temperature` | Same enum values, different domain |
| `open_threads` | `open_threads` | Identical |
| `trait_evidence` table | `trait_evidence` table | Identical structure, different dimension names in payload |
| `contradictions` table | `contradictions` table | Identical, this becomes the insights mechanic |
| `InterviewerSession` | `VibSession` | Rename only |
| `Soul Cartographer` (10 personality dims) | `Vib Cartographer` (10 wellness state dims, § 7) | Same code, swapped dimensions |
| `Move Generator` (8 dating moves) | `Move Generator` (8 wellness moves + 2 new, § 8) | Same pipeline, swapped move set |
| `mirror` persona context | `companion_voice` persona context | Rename, narrower purpose |
| `vib` persona context (twin sent out) | DELETED | No other souls |
| `vib/` package | DELETED | |
| `world/` package | DELETED | |

---

## 7. New Cartographer dimensions (the new "10")

The Cartographer's job is unchanged: maintain a model of the user across
N dimensions, each with a value, confidence, and evidence count, with
contradictions surfaced when trust is high. The dimensions change.

These are the new 10. Each has the same structure as the old personality
dimensions (`{value, confidence, evidence_count, contradictions}`).
Values are typically a small categorical or a 0..1 float; the value
type is documented per-dimension.

1. **`mood_baseline`** — float 0..1. Smoothed average mood reading over
   trailing 28d. Evidence: every `mood` entry. Confidence rises with
   entry density.
2. **`mood_volatility`** — categorical: `steady | moderate | volatile`.
   How much the user's mood swings within a day. Evidence: variance of
   `mood` entries within the same day, accumulated.
3. **`sleep_pattern`** — categorical: `consistent | irregular | poor`.
   Evidence: `sleep` entries plus inferred sleep windows from late/early
   activity.
4. **`hunger_relationship`** — float 0..1, where 0 = highly distressed
   relationship with hunger, 1 = neutral/comfortable. Evidence: meal
   satisfaction patterns, time-since-eat gaps, frequency of binge_marker
   entries, language used in meal logs.
5. **`food_preferences`** — structured: list of `{food, frequency,
   sentiment}`. Evidence: meal entries, `liked_foods` from user.
6. **`risk_window_pattern`** — structured: list of `{day_of_week,
   hour_range, confidence}`. The user-specific high-risk windows. Evidence:
   binge_marker timestamps clustering.
7. **`movement_pattern`** — categorical: `active | moderate | sedentary`.
   Evidence: walk and sunlight entries.
8. **`social_pattern`** — categorical: `connected | intermittent |
   isolated`. Evidence: `social` entries, frequency.
9. **`stressor_signals`** — structured: list of `{stressor, evidence_count,
   sentiment}`. What the user has named as making things harder. Evidence:
   notes, mood logs with text, conversation extracts. (Examples for
   Sheltron specifically: trading P&L days, late nights, weekends without
   plans.)
10. **`response_style`** — structured: `{preferred_message_length,
    formality, humor_tolerance, hedging_preference}`. How Vib should
    speak to *this* user. Built up by `persona_builder.py` from the
    user's own messages.

The Cartographer's evidence-first architecture means each entry the
user logs naturally contributes to one or more of these dimensions,
with confidence rising as data accumulates. **Demonstrated signals are
worth 2x stated signals**, same as before — a logged binge is stronger
evidence than a self-report of "I sometimes binge."

---

## 8. New Move Generator (the new 8 + 2 moves)

The pipeline stays: eligibility check → emotional override ("presence
beats progress") → weighted scoring → selection. The scoring weights
stay the same (flow 0.3, data need 0.2, variety 0.35, phase fit 0.15).
The moves change.

| Move | Renamed from | Purpose | Eligibility | Notes |
|---|---|---|---|---|
| `acknowledge` | (new) | Brief, neutral confirmation of a log or statement | Always | Default move for the logging side-channel. One sentence max. |
| `open_door` | `open_door` | Gentle invitation to share more about state or feeling | Trust ≥ 0.3, no recent open_door | Identical to dating Vib's version, scoped to wellness topics |
| `follow_thread` | `follow_thread` | Continue a topic the user just brought up | An open thread exists, not exhausted (<3 in a row) | Identical mechanic |
| `observation` | `observation` | Vib notices something specific about state | At least one wellness dimension has confidence ≥ 0.5 | "You're a little quieter than usual tonight." |
| `gentle_offer` | `hypothetical` (renamed/repurposed) | Suggest an outing, walk, or specific small action | Suggestion engine returns a valid suggestion (§ 14 of v1-spec) | The "let's go to the Circle K" move |
| `pattern_callback` | `gentle_contradiction` (renamed) | Surface a noticed pattern from contradictions table | Trust ≥ 0.7, phase ∈ {ATTUNED, COMPANION}, NEVER in `acute` post-binge mode, NEVER in `soft_morning` post-binge mode | The indirect-confrontation mechanic. Used in insights. |
| `callback` | `callback` | Reference an earlier conversation | An old thread has resurfacing relevance | Identical |
| `validate` | `share` (repurposed) | Acknowledge difficulty without trying to fix it | High emotional temperature OR low mood | "Yeah. That's a hard one." Replaces the dating Vib's "share a personal anecdote" because Vib has no anecdotes. |
| `state_check` | (new) | One-tap mood query before a meal log | User is about to log a meal AND no mood entry in the last 2h | The "mood before food" mechanic. |
| `rest` | `rest` | Stay quiet, hold space, end turn without forcing engagement | Always available; default in `acute` post-binge mode after the first acknowledgment | Identical to dating Vib's `rest` |

10 moves total. The scoring system handles the rest.

**Banned moves in `acute` post-binge mode** (enforced by middleware,
not move scoring): everything except `acknowledge`, `validate`, `rest`,
and `gentle_offer` (where the offer is restricted to non-food).

**Banned moves in `soft_morning` mode**: `pattern_callback` (always),
`gentle_offer` where the offer is food-related.

---

## 9. New base persona for prompt_builder

Replace the existing "sharp friend, NOT therapist" base persona with
the text in `prompts/vib-system-prompt.md`. The full system prompt is
already written and is stack-agnostic. The prompt_builder layers on
top of it the same way it does today: phase prompt + move style guide
+ dynamic move context + invisible metadata block + hard constraints.

The hard constraints list gets the wellness-specific banned phrases
appended:
- "Great choice!" / "Awesome!" / "Amazing!"
- "Let's crush it" / "You got this" / "On track"
- "Make up for it" / "Earn it back" / "Fresh start" / "New day"
- "Sorry to hear that" / "I understand how you feel"
- "Goal," "target," "score," "rank," "win," "lose"

Plus the existing dating-Vib banned phrases ("as an AI", "interesting",
"I love that") which still apply.

---

## 10. Vision routing (the photo → macros path)

Your `llm_client.py` already has model routing across three tiers:
interviewer, cartographer, mirror. Add a fourth: **vision**.

```python
# llm_client.py — additions

class ModelTier(str, Enum):
    INTERVIEWER = "interviewer"
    CARTOGRAPHER = "cartographer"
    MIRROR = "mirror"
    VISION = "vision"             # NEW

DEFAULT_MODELS = {
    ModelTier.INTERVIEWER: os.getenv("VIB_MODEL", "qwen3.5:9b"),
    ModelTier.CARTOGRAPHER: os.getenv("VIB_MODEL_CARTOGRAPHER",
                                       os.getenv("VIB_MODEL", "qwen3.5:9b")),
    ModelTier.MIRROR: os.getenv("VIB_MODEL_MIRROR",
                                 os.getenv("VIB_MODEL", "qwen3.5:9b")),
    ModelTier.VISION: os.getenv("VIB_MODEL_VISION", "qwen2.5-vl:7b"),  # NEW
}

DEFAULT_PARAMS = {
    ModelTier.INTERVIEWER: {"temperature": 0.75, "num_predict": 256},
    ModelTier.CARTOGRAPHER: {"temperature": 0.3,  "num_predict": 512},
    ModelTier.MIRROR:      {"temperature": 0.8,  "num_predict": 256},
    ModelTier.VISION:      {"temperature": 0.2,  "num_predict": 512},  # NEW: low temp for structured output
}
```

Then add a `vision()` method to `OllamaLLMClient` that takes a base64
image + caption and returns parsed JSON. Ollama's HTTP API supports
images for vision models — pass them in the `images` field of the
generate/chat call.

**Why qwen2.5-vl:7b:** it's the same family as qwen3.5 (so the install
story is `ollama pull qwen2.5-vl:7b` and you're done), it runs on
modest hardware, it's vision-capable, and you don't break the local-only
privacy story. Recommendation locked.

**If qwen2.5-vl performance is bad** for food-specifically: fall back to
`llava:13b` or `bakllava` as a second option, both also Ollama-pullable.
If both are bad, the third fallback is to add a `vision_fallback` route
that calls a hosted vision model (Claude/GPT-4o-mini) for *photos only*,
keeping all conversation local. The router structure makes this swap a
one-line config change.

The `vision_service.py` in the new `vib_wellness/` package wraps this:

```python
async def estimate_macros_from_photo(
    image_bytes: bytes,
    caption: str | None,
    user_id: str,
) -> MealEstimate:
    image_b64 = base64.b64encode(image_bytes).decode()
    raw = await llm_client.vision(
        prompt=VISION_PROMPT,           # see prompts/vision_food.txt
        image_b64=image_b64,
        caption=caption,
    )
    parsed = parse_meal_json(raw)       # multi-step JSON fallback like cartographer
    return parsed
```

The vision prompt should ask for: a one-line description, a list of
detected items with portions, estimated macros (protein/cal/carbs/fat),
and a confidence score 0..1. Conservative estimates by default. If
confidence < 0.4, the UI shows the user "I'm not sure I see this right
— want to fix anything?" before logging.

---

## 11. Post-binge protocol middleware

A small module in `vib_wellness/post_binge.py` that sits between the
WebSocket handler and `VibSession.process_turn()`. Its job: read the
current `post_binge_mode` from `CartographerState`, and if set, modify
the move set and tone sliders before the turn proceeds.

```python
# vib_wellness/post_binge.py

from interviewer.models import MoveType, ToneSliders

ACUTE_ALLOWED_MOVES = {
    MoveType.ACKNOWLEDGE,
    MoveType.VALIDATE,
    MoveType.REST,
    MoveType.GENTLE_OFFER,   # non-food only — enforced by gentle_offer's own logic
}

SOFT_MORNING_BANNED_MOVES = {
    MoveType.PATTERN_CALLBACK,
}

def apply_post_binge_protocol(
    state: CartographerState,
    eligible_moves: set[MoveType],
    tone: ToneSliders,
) -> tuple[set[MoveType], ToneSliders]:
    if state.post_binge_mode == "acute":
        eligible_moves = eligible_moves & ACUTE_ALLOWED_MOVES
        tone = ToneSliders(
            proximity="intimate",
            energy="quiet",
            directness="hedged",
        )
    elif state.post_binge_mode == "soft_morning":
        eligible_moves = eligible_moves - SOFT_MORNING_BANNED_MOVES
        tone = ToneSliders(
            proximity="intimate",
            energy="quiet",
            directness="hedged",
        )
    return eligible_moves, tone
```

This is called in `orchestrator.py` right after eligibility check and
right before scoring. It is the *only* place where moves are removed by
hardcoded rule rather than by the scoring system. Everything else stays
in the move generator.

The state transitions:
- `binge_marker` entry logged → set `post_binge_mode = "acute"`,
  `post_binge_until = now + 4h`.
- A scheduled job (or a check on next turn) at the 4h mark sets
  `post_binge_mode = "soft_morning"`, `post_binge_until = midnight + 24h`
  (in user's TZ).
- 24h after entering soft_morning, clear both fields.

---

## 12. Storage additions (SQLite)

Add to `interviewer/storage.py`. Run as a one-shot migration the first
time the new code starts up.

```sql
-- migrations/001_add_wellness_tables.sql

-- The polymorphic log
CREATE TABLE IF NOT EXISTS entries (
  id              TEXT PRIMARY KEY,
  soul_id         TEXT NOT NULL,
  kind            TEXT NOT NULL,
  -- 'meal' | 'mood' | 'water' | 'sleep' | 'walk' | 'sunlight' | 'social' |
  -- 'weight' | 'purchase' | 'binge_marker' | 'note'
  payload_json    TEXT NOT NULL,
  at              TEXT NOT NULL,           -- ISO timestamp, when it happened
  logged_at       TEXT NOT NULL,           -- ISO timestamp, when it was logged
  source          TEXT NOT NULL,
  -- 'voice' | 'photo' | 'tap' | 'scan' | 'proactive' | 'manual'
  confidence      REAL NOT NULL DEFAULT 1.0,
  tagged_as_binge INTEGER,                 -- nullable; for meal entries
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS entries_soul_at_idx
  ON entries (soul_id, at DESC);
CREATE INDEX IF NOT EXISTS entries_soul_kind_idx
  ON entries (soul_id, kind, at DESC);
CREATE INDEX IF NOT EXISTS entries_soul_binge_idx
  ON entries (soul_id, at DESC)
  WHERE kind = 'binge_marker' OR tagged_as_binge = 1;

-- VibState cache (one row per soul)
CREATE TABLE IF NOT EXISTS vib_state (
  soul_id              TEXT PRIMARY KEY,
  state_json           TEXT NOT NULL,
  attunement_confidence REAL NOT NULL DEFAULT 0.5,
  post_binge_mode      TEXT,                -- NULL | 'acute' | 'soft_morning'
  post_binge_until     TEXT,                -- ISO timestamp
  recomputed_at        TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

-- Risk windows (learned per user)
CREATE TABLE IF NOT EXISTS risk_windows (
  id          TEXT PRIMARY KEY,
  soul_id     TEXT NOT NULL,
  day_of_week INTEGER NOT NULL,             -- 0..6
  hour_start  INTEGER NOT NULL,             -- 0..23
  hour_end    INTEGER NOT NULL,             -- 1..24
  confidence  REAL NOT NULL DEFAULT 0.5,
  hit_count   INTEGER NOT NULL DEFAULT 0,
  updated_at  TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS risk_windows_soul_idx ON risk_windows (soul_id);

-- Nudges (rate-limit + audit Vib's proactive messages)
CREATE TABLE IF NOT EXISTS nudges (
  id          TEXT PRIMARY KEY,
  soul_id     TEXT NOT NULL,
  sent_at     TEXT NOT NULL,
  reason      TEXT NOT NULL,
  message_id  TEXT,
  responded   INTEGER,                      -- 0/1/null
  acted_on    INTEGER,                      -- 0/1/null
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE,
  FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE INDEX IF NOT EXISTS nudges_soul_sent_idx
  ON nudges (soul_id, sent_at DESC);

-- Store cache (for the suggestion engine)
CREATE TABLE IF NOT EXISTS store_items (
  id            TEXT PRIMARY KEY,
  soul_id       TEXT NOT NULL,
  store_name    TEXT NOT NULL,
  item_name     TEXT NOT NULL,
  macros_json   TEXT NOT NULL,
  price_cents   INTEGER,
  last_seen_at  TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS store_items_soul_store_idx
  ON store_items (soul_id, store_name);

-- Shortcuts (tap-to-log)
CREATE TABLE IF NOT EXISTS shortcuts (
  id          TEXT PRIMARY KEY,
  soul_id     TEXT NOT NULL,
  kind        TEXT NOT NULL,
  label       TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  use_count   INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL,
  FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS shortcuts_soul_kind_idx
  ON shortcuts (soul_id, kind);

-- Extend the souls table with macro targets, budget, sidekick name, prefs
ALTER TABLE souls ADD COLUMN macro_targets_json TEXT;
ALTER TABLE souls ADD COLUMN food_budget_cents INTEGER;
ALTER TABLE souls ADD COLUMN food_budget_period_days INTEGER DEFAULT 7;
ALTER TABLE souls ADD COLUMN food_budget_period_start TEXT;
ALTER TABLE souls ADD COLUMN sidekick_name TEXT DEFAULT 'Vib';
ALTER TABLE souls ADD COLUMN quiet_hours_start TEXT DEFAULT '22:00';
ALTER TABLE souls ADD COLUMN quiet_hours_end TEXT DEFAULT '08:00';
ALTER TABLE souls ADD COLUMN max_nudges_per_day INTEGER DEFAULT 2;
ALTER TABLE souls ADD COLUMN timezone TEXT DEFAULT 'America/New_York';
```

Existing tables to keep AS-IS: `souls`, `sessions`, `messages`,
`trait_evidence`, `contradictions`, `soul_state`. Drop `vib_sessions`,
`vib_messages`, `vib_results` from the dating-Vib soul-to-soul engine.

---

## 13. WebSocket protocol changes

**Delete these client→server messages:** `start_vib`, `send_vib_out`,
`run_world_day`, `run_world_day_spatial`.

**Delete these server→client messages:** `vib_turn`, `vib_result`,
`match_found`.

**Add these client→server messages:**

```ts
{ type: "log_meal", payload: { name, description?, photo_id?, macros?, items?, cost_cents?, at? } }
{ type: "log_mood", payload: { reading, label?, note?, at? } }
{ type: "log_water", payload: { ml, at? } }
{ type: "log_sleep", payload: { duration_h, quality?, at? } }
{ type: "log_walk", payload: { duration_min?, distance_km?, where?, at? } }
{ type: "log_sunlight", payload: { duration_min?, source, at? } }
{ type: "log_social", payload: { kind, who?, note?, at? } }
{ type: "log_purchase", payload: { store, items, total_cents, receipt_photo_id?, at? } }
{ type: "log_binge", payload: { note?, severity?, at? } }
{ type: "tag_meal_as_binge", payload: { entry_id } }
{ type: "request_state" }                  // returns current VibState
{ type: "request_insights" }                // returns the weekly insights view
{ type: "dismiss_nudge", payload: { nudge_id } }
{ type: "snooze_vib", payload: { duration: "4h" | "today" | "weekend" } }
```

**Add these server→client messages:**

```ts
{ type: "entry_logged", payload: { entry_id, ack_message? } }
{ type: "state_update", payload: { state: VibState } }
{ type: "nudge", payload: { message, reason, suggestion? } }
{ type: "insight", payload: { week_summary, observations } }
{ type: "post_binge_mode_change", payload: { mode: "acute" | "soft_morning" | null } }
```

The HTTP endpoint `POST /upload/photo` is multipart, returns
`{ photo_id, width, height }`. The `log_meal` and `log_purchase`
messages reference photos by ID rather than embedding base64 in the
WebSocket frame.

---

## 14. Frontend (`static/`) changes

You have a working chat UI and entry screen. Extend, don't replace.

**Reuse:**
- Entry screen (name input → soul lookup) — keep, this is your auth.
- Interview chat UI → becomes the conversation thread with Vib.
- Soul panel → becomes the wellness state panel (current dimensions
  with confidence bars).

**Add new screens:**

1. **Home** (the new default after entry):
   - Greeting strip ("Morning, Sheltron")
   - Mood orb (one tap → 6-option grid → log)
   - Day-touched trio (☀ 👣 💬)
   - Macro arcs (4 soft progress arcs)
   - Budget line ($X left this week)
   - Big "Talk to Vib" button → opens conversation thread
   - Recent log feed (last 3-5 entries)

2. **Logging modal** (slides up from anywhere):
   - 4 buttons: 🎙 Talk · 📷 Photo · 👆 Tap · 🛒 Scan
   - Voice uses browser SpeechRecognition API (free, on-device on most
     platforms). Sends transcript via `log_meal` with source: "voice".
   - Photo uses native `<input type="file" accept="image/*" capture>`,
     uploads to `POST /upload/photo`, then sends `log_meal` with the
     photo_id.
   - Tap shows the user's shortcuts list.
   - Scan uses the browser's `BarcodeDetector` API (Chrome/Android, with
     fallback to a JS library for iOS Safari which doesn't support it
     natively).

3. **Insights view** (small icon, intentionally buried):
   - Vib's 3-5 sentence weekly observation
   - Soft area chart of macros
   - Sparkline of mood
   - Day-touched grid

**Frontend stack:** stay vanilla JS for v1. You already have the
WebSocket client and the chat UI working — adding new screens is a few
hundred lines of HTML/CSS/JS. PWA manifest + service worker for
installability and push (you said it's already PWA-ready). React/Vue
later if complexity demands it; right now they don't.

**Aesthetic direction:** soft, low-contrast, generous whitespace,
muted colors, single accent color for Vib (suggest a warm dusty rose
or muted sage — not blue, not red). No icon-heavy navigation. The
home screen should feel like an empty notebook page, not a dashboard.

---

## 15. Execution order — week by week

### Week 1 — The pivot itself (mostly delete + rename)

- **Day 1**: Branch, tag, delete `vib/` and `world/` packages, delete
  the dead WebSocket handlers, delete the dead frontend screens. Run
  the existing tests; expect a bunch to fail; delete the failing ones
  that are testing deleted code.
- **Day 2**: Rename `Phase` enum values, rename `InterviewerSession` →
  `VibSession`, rename `trust_score` → `attunement_confidence` (or
  alias and keep both). Update all references.
- **Day 3**: Rewrite `interviewer/models.py` Cartographer dimensions
  (the new 10). Update `Cartographer` analyzer code to populate the
  new dimensions from the new evidence types.
- **Day 4**: Rewrite the move set in `move_generator.py` (the new 8+2).
  Add the new moves. Update eligibility rules. Rewrite the move style
  guide files in `prompts/`.
- **Day 5**: Rewrite the base persona using `vib-system-prompt.md`.
  Rewrite the 4 phase prompts. Update the metadata block in
  `prompt_builder.py` to include wellness state fields.
- **Day 6**: Run the migration to add new tables. Wire up `log_meal`
  end-to-end through the WebSocket: client sends → server writes entry
  → state recomputes → Vib responds with one acknowledge move. This is
  the first new feature working.
- **Day 7**: Use it on yourself for a day. Voice-log every meal. Find
  everything that's broken or annoying. Don't fix it yet — write it down.

### Week 2 — Vision + post-binge protocol

- **Day 8**: Pull qwen2.5-vl:7b. Add the VISION tier to llm_client.py.
  Write `vision_service.py`. Test on photos of food from your phone.
- **Day 9**: Wire up the `POST /upload/photo` endpoint. Wire up the
  photo logging path through the frontend. Use it to log a few meals.
- **Day 10**: Write `vib_wellness/post_binge.py` middleware. Insert it
  into `orchestrator.process_turn()`. Write the state-transition logic
  for acute → soft_morning → cleared.
- **Day 11**: Test the post-binge protocol. Log a binge_marker. Verify
  Vib responds correctly in acute mode. Wait until next morning. Verify
  the soft_morning message lands correctly. This is the most important
  test of the whole project.
- **Day 12**: Port the receipt parser from your Base44 work into
  `vib_wellness/receipt_parser.py`. Wire it up as a path within the
  photo logging endpoint.
- **Day 13**: Mood-before-meal gate. The `state_check` move triggers
  when the user is about to log a meal and there's no recent mood entry.
- **Day 14**: Use it on yourself for a full week. Log everything. Note
  every place Vib's tone slipped into moralizing or performance language.
  Tune the prompts.

### Week 3 — Nudges + insights + suggestion engine

- **Day 15**: Write `nudge_service.py` as an asyncio task in the FastAPI
  app, runs every hour. Reads VibState for each user, decides if there's
  anything specific to say, and if so calls move_generator with
  `proactive=True`.
- **Day 16**: Wire up the suggestion engine: `gentle_offer` move when
  scored high enough, with the 4 conditions (weather, food gap,
  destination, item fit). Seed the store_items table manually with
  3-5 stores you actually use.
- **Day 17**: Write `insights_service.py`. Weekly view, observational,
  uses the contradictions table for pattern callbacks.
- **Day 18**: Build the insights frontend screen.
- **Day 19**: Build the home dashboard with macro arcs and the
  day-touched trio. This is the new default landing after entry.
- **Day 20**: Build the logging modal with all 4 input methods.
- **Day 21**: Use it on yourself for the third week. By now Vib has
  3 weeks of your data and the insights pass should produce something
  meaningful.

### Week 4 — Polish + first testers

- **Day 22**: Style pass. Soft aesthetic. Mobile responsive (PWA).
- **Day 23**: PWA install flow. Push notification hookup via the Push
  API + a service worker.
- **Day 24-25**: Quiet hours, snooze, settings screen. Edit macro
  targets, budget, sidekick name.
- **Day 26**: Recruit 5 testers personally. People you know who
  fit the use case (not strangers). One at a time, in person if
  possible, walk them through the first session.
- **Day 27-28**: Watch them use it. Take notes. Don't fix things in real
  time — collect everything, then triage.

After day 28: decide. Keep iterating with the small group, ship to
TestFlight publicly, or pause. No hard deadline.

---

## 16. Validation checklist

You'll know the pivot is healthy when ALL of these are true:

- [ ] You delete the `vib/` and `world/` packages and the existing
      tests still pass for the interviewer system (or fail only on
      tests that were specifically about the deleted code).
- [ ] You rename the phases and a returning user from dating-Vib still
      loads (because soul_id and trait_evidence persist). The
      Cartographer reloads them with the new dimensions overlaid.
- [ ] You can voice-log a meal and Vib acknowledges in one sentence
      with no praise, no warning, no exclamation marks.
- [ ] You can take a photo of a plate of food and the vision pipeline
      returns macros within 3 seconds, with confidence visible in the
      UI.
- [ ] You log a `binge_marker` and Vib's next message follows the
      acute protocol exactly: acknowledgment + one open question +
      no mention of tomorrow / macros / making up.
- [ ] The next morning's first message is gentle and does not reference
      the binge or use any of the banned phrases.
- [ ] The nudge cron runs and goes silent on most hours. You go a full
      day without a nudge if the day was unremarkable.
- [ ] The weekly insights view produces an observation that is a
      *pattern*, not a verdict, and is phrased with curiosity.
- [ ] You use it for 30 days yourself without it feeling like a chore.
- [ ] At least one external tester says, unprompted, "this feels
      different from other apps."

If all 10 are true, you have a real product. Ship it to TestFlight (or
the equivalent PWA install path), keep growing slowly.

---

## End

This is everything. Branch, delete, rename, extend, test, repeat.
80% of the spine already exists. The remaining 20% is logging + vision
+ nudges + a hardcoded protocol. You can be using a real working version
of wellness Vib on yourself by end of week 1.
