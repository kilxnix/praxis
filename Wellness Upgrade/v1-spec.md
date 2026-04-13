# Vib v1 — Product Spec

This is the product spec: what the user sees, how the daily loop feels,
what ships in v1 and what doesn't. The implementation plan (file-by-file
deletes/renames/adds, the SQLite migrations, the move remap, the
execution order) is in `wellness-pivot-plan.md`. This document stays
focused on the *product*.

## What v1 is

A PWA running on top of the existing Vib FastAPI server. Three new
frontend screens layered onto the existing chat UI. New WebSocket
message types for logging. A polymorphic entries log in SQLite. A
hardcoded post-binge protocol middleware in front of the orchestrator.
That's it. Everything else is post-v1.

## The screens

### 1. Home (the new default after entry)

One screen. No tabs. No menu. Top to bottom:

- **Greeting strip.** "Morning, Sheltron." Single line, time-of-day aware.
- **Mood orb.** A soft-colored circle. Tap once → 6-option grid of
  feeling-words (never a 1–10 scale). Color shifts subtly to reflect the
  current reading.
- **Day-touched trio.** Three small dots: ☀ sunlight, 👣 movement,
  💬 social. Each fills in when there's evidence the dot was touched.
  No streaks. No rewards. Just a quiet visual record of the day so far.
- **Macro arcs.** Soft progress arcs for the macros the user cares
  about (default: protein, calories). Numerical values only on tap.
  Arcs never turn red. Over-goal looks the same as on-goal.
- **Budget line.** "$X left this week." One line. Tap to expand.
- **Talk-to-Vib button.** Big, soft, bottom of the screen. Tap it,
  conversation thread slides up. (This is the existing chat UI.)
- **Recent log feed.** Last 3–5 entries, scrollable. What + when. No
  judgment, no color-coding.

### 2. Logging (slides up from anywhere)

Four buttons, big, edge-to-edge:

- **🎙 Talk** — browser SpeechRecognition API → transcript → `log_meal`
  WebSocket message with source: "voice".
- **📷 Photo** — native `<input type="file" accept="image/*" capture>`
  → `POST /upload/photo` → `log_meal` with photo_id. Server runs the
  vision pipeline (qwen2.5-vl) and returns estimated macros for the
  user to confirm/correct.
- **👆 Tap** — list of the user's shortcuts (frequent foods, frequent
  moods, frequent activities). One tap → logged.
- **🛒 Scan** — `BarcodeDetector` API where supported (Chrome/Android),
  fallback library for iOS Safari. Multiple scans in one session = one
  `log_purchase` event for the grocery trip.

Logging is the most-used flow. It must be fast. No screen in the
logging flow should require more than two taps to complete a normal
entry.

### 3. Conversation with Vib (the existing chat UI, repurposed)

The existing chat thread, lightly restyled. Persistent, scrolls back
forever. This is where:

- The user talks to Vib at any time.
- Vib's proactive nudges arrive — as messages in the thread, with a
  push notification that says only "Vib nudged you."
- Quick log acknowledgments appear ("logged: chicken wrap, ~38g protein").
- Morning and evening check-ins live.

The conversation is the center of gravity. The home screen is a
dashboard; the conversation is the relationship.

### 4. Insights (intentionally buried — small icon)

A weekly view, observational only, no scoring. Vib writes 3–5 sentences
about what it noticed:

> "This week you went outside on the days you slept more than 7 hours,
> every time. Saturday was harder — that pattern's been there for a few
> weeks. The three days you talked to a person were also the three days
> your mood trended up by evening."

Plus optional small charts: macros over the week as a soft area chart,
mood as a sparkline, day-touched dots as a grid. **No numbers comparing
this week to last.** No "you did better/worse." Patterns, not grades.

This view is also where the **gentle pattern callbacks** live — the
`pattern_callback` move from the move generator. Driven by the
existing `contradictions` table (which already implements "noticed
patterns surfaced gently when trust is high" — that mechanic transfers
literally).

## The daily loop, in plain English

**Morning.** Vib sends a single message: time-of-day, weather, sleep
read (if Vib has it), one specific small thing. "Morning. 58 and sunny.
You slept 6h, light. Macros are fresh. Want me to remind you to step
outside before noon?" One message. No checklist.

**Meals.** The user logs however is fastest. Vib acknowledges in one
sentence, asks at most one clarifying question, and stops talking.
*Acknowledges, not praises.* Internally this is the new `acknowledge`
move triggered by the logging side-channel in `process_turn()`.

**Mid-afternoon, if conditions are right.** Vib reaches out with a
*destination suggestion* via the `gentle_offer` move. The conditions
(weather acceptable + real food gap + real destination + item that
fits) are checked by the suggestion engine before the move is even
considered eligible. Most days this doesn't fire. That's correct.

**Risk window (evening / weekend).** Vib has a list of high-risk
windows that it learns over time (default seed: Friday 8pm–midnight,
Saturday 7pm–midnight, Sunday after 9pm, the day after a logged
binge). When the clock enters one of these windows AND mood is below
baseline, Vib reaches out with a *non-food* suggestion. "Hey. Saturday
night. How are you feeling? Want to put something on?" The risk
windows live in the `risk_windows` table and are updated by the daily
attunement pass.

**After a binge.** The user self-tags with `tag_meal_as_binge` or
sends `log_binge`. The post-binge middleware sets `post_binge_mode =
"acute"`. The next move is restricted to acknowledge / validate / rest /
non-food gentle_offer. The morning after, the mode flips to
`soft_morning` for 24h. See `vib-layer.md` § Post-binge protocol for
the full rule set. **The middleware is hardcoded; it does not delegate
this to the model.**

**Evening.** Vib checks in at most once, around 1–2h before the user's
usual sleep. Brief. "Long day. How's the body feeling?" Optional. If
they don't respond, it doesn't ask again.

## The suggestion engine

The `gentle_offer` move only fires when ALL of these are true:

1. Weather is acceptable AND daylight remains AND user hasn't been
   outside today (OR mood reading is below baseline).
2. There's a real food gap (a macro the user is meaningfully short on)
   OR the user has budget room and hasn't eaten in 3+ hours.
3. There's a real destination within reasonable distance from a
   user-supplied frequent_stores list.
4. The destination has at least one item that fits the gap (from the
   per-user `store_items` cache, refreshed weekly).

If all four: "It's nice out, you're 25g protein short, and you have
$11 left this week. Want to walk to the Circle K — about 8 minutes —
and grab a couple Fairlifes?"

If any false: Vib stays quiet. It does not invent reasons to go outside.

## What gets logged

Every log writes one row to the polymorphic `entries` table. Kinds:

- `meal` — payload: name, description, photo_id?, macros, items?, cost_cents?
- `mood` — payload: reading (0..1), label, note?
- `water` — payload: ml
- `sleep` — payload: duration_h, quality?
- `walk` — payload: duration_min?, distance_km?, where?
- `sunlight` — payload: duration_min?, source ('auto'|'manual')
- `social` — payload: kind ('in_person'|'phone'|'text'|'video'), who?, note?
- `weight` — payload: lbs?, kg? (off by default, never displayed in main UI)
- `purchase` — payload: store, items[], total_cents, receipt_photo_id?
- `binge_marker` — payload: note?, severity?
- `note` — payload: text

The `binge_marker` kind is the one that trips the post-binge protocol.
**Only the user tags it.** Vib never decides for the user what counts.

## Notification rules (locked)

- At most **two proactive nudges per day** in normal weeks.
- At most **three** during a logged stressful period.
- Notifications are short: "Vib nudged you." The actual content is in
  the thread. Intentional — makes the notification feel anticipated,
  not intrusive.
- **Quiet hours** are user-configurable, default 10pm–8am. Vib never
  initiates contact during quiet hours.
- **Snooze** is one tap from any nudge: snooze for 4h, today, or
  the weekend.

Implementation note: the nudge service is an asyncio task in the
FastAPI app, runs every hour, reads `vib_state` per soul, and only
fires when the rate limit allows AND a `gentle_offer` or `observation`
move scores high enough to be worth sending.

## What v1 explicitly does NOT have

- No social features. No friends. No sharing. No leaderboards.
- No streaks. No badges. No challenges.
- No restrictive diets, "plans," or coaching curricula.
- No paywall. No premium tier.
- No web app version separate from the PWA. Mobile-installable PWA only.
- No native iOS/Android wrapper (yet). PWA is enough for v1.
- No wearable integration (yet). Manual entry beats half-working.
- No medical claims. Anywhere. The app is a wellness companion, not a
  treatment, and the install screen says so.

## Stack (existing + additions)

- **Backend:** FastAPI / Uvicorn (existing).
- **DB:** SQLite WAL mode (existing). New tables added via migration.
- **LLM:** Ollama with qwen3.5:9b for chat (existing), qwen2.5-vl:7b
  for vision (new).
- **Frontend:** vanilla JS PWA (existing chat UI extended with new
  screens). Service worker for push notifications.
- **STT for voice logging:** browser SpeechRecognition API. Free,
  on-device on most platforms. No Whisper, no Deepgram.
- **Barcode scanning:** browser BarcodeDetector API + fallback library
  for iOS Safari.

Nothing new in the stack except qwen2.5-vl. That's the whole point of
the pivot working: the dating Vib already has the right shape.

## Success criteria for v1

Three things, in order:

1. **The founder uses Vib daily for 30 days without it feeling like a
   chore.** If this fails, nothing else matters.
2. **The founder's binge frequency is unchanged or lower over those 30
   days, AND the founder feels less alone in the moment.** Both, not
   either. If Vib reduces binges by being a stricter tracker, that's
   a failure of design even if the number went down.
3. **5 external testers use it for 14 days and at least 2 of them ask,
   unprompted, when it'll be available to others.** That's the first
   real signal.

If all three: ship the PWA install link publicly, start the slow-grow
path. If 1 and 2 but not 3: keep iterating. If 1 fails: the core loop
is wrong, rebuild it.

## What's in this kit, where to look

- `wellness-pivot-plan.md` — file-by-file pivot plan (read first for
  *how* this gets built).
- `v1-spec.md` — this file (the *what*).
- `vib-layer.md` — the attunement state model and the hardcoded
  post-binge protocol (the *why* certain rules are non-negotiable).
- `prompts/vib-system-prompt.md` — Vib's voice and rules (drops into
  prompt_builder as the new base persona).
- `README.md` — overview and run instructions.
