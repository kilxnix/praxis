# The Vib Layer

The attunement layer ported from the old Vib (Soul) codebase. This is the
spine of the product. Everything Vib says is a function of what this
layer believes about your current state.

## What it is, in one paragraph

A continuously updated model of your state across multiple dimensions —
mood, energy, sleep debt, hunger satisfaction, time-of-day, day-of-week,
weather context, recent food log, recent activity, recent social touch,
and an internal "attunement score" representing how confident Vib is
that it understands where you're at right now. Every Vib utterance —
proactive nudge, reply in conversation, log acknowledgment — is
*modulated* by this state. It is the difference between a chatbot that
sounds friendly and a companion that actually notices you.

## How it differs from the old Vib

The Soul-era Vib modeled compatibility between two humans. It tracked
each person's state and looked for patterns in the *interaction* — where
they aligned, where they diverged, where one was leading and the other
following. The state model itself (the per-person attunement) was the
reusable spine.

In wellness Vib, there is only one human. The "compatibility negotiation"
becomes "self-attunement negotiation": Vib tracks your state, compares
it to a moving baseline of *you over the past few weeks*, and flags
divergences that matter. When today's state is meaningfully off your
baseline, Vib's tone shifts. The mechanic is the same. The target changed.

## The state model

The Vib layer maintains a single object per user, updated in real time as
new entries land. Keep this lean — every field has to earn its place.

```ts
interface VibState {
  // Time and context
  now: ISODateTime;
  local_hour: number;          // 0-23 in user's timezone
  day_of_week: number;         // 0-6
  weather: { temp_f: number; conditions: string; daylight_remaining_h: number } | null;

  // Mood (rolling)
  mood_now: MoodReading | null;       // most recent mood log
  mood_trend_24h: "up" | "flat" | "down" | "unknown";
  mood_trend_7d: "up" | "flat" | "down" | "unknown";
  mood_baseline: number;              // 0-1, smoothed average mood over the trailing 28d

  // Sleep
  sleep_last_night_h: number | null;
  sleep_debt_3d: number;              // hours below 7h, summed over the last 3 nights

  // Food state
  macros_today: { protein_g: number; cal: number; carbs_g: number; fat_g: number };
  macro_targets: { protein_g: number; cal: number; carbs_g: number; fat_g: number };
  hours_since_last_meal: number;
  meals_today: number;
  meal_satisfaction_rolling: number;  // 0-1, "did the user feel good after eating" rolling avg

  // Body
  hunger_signal_estimate: "low" | "med" | "high" | "unknown";  // inferred from time-since-eat + macro state
  energy_signal_estimate: "low" | "med" | "high" | "unknown";  // inferred from sleep + mood + time-of-day

  // Day-touched
  sunlight_today: boolean;
  movement_today: boolean;
  social_today: boolean;

  // Budget
  food_budget_remaining: number;
  budget_period_days_left: number;

  // Risk
  in_risk_window: boolean;            // is right now in a known high-risk window for this user?
  days_since_last_binge_marker: number | null;
  post_binge_mode: PostBingeMode | null;  // see Post-binge protocol

  // Attunement
  attunement_confidence: number;       // 0-1, how sure are we about all of the above
  needs_check_in: boolean;             // true when confidence is low and we should ask
}
```

## The modulation rules (how state shapes tone)

Every Vib utterance passes through the modulation layer before it leaves
the system prompt context. The rules below are not exhaustive — they're
the locked starting set, and they should be tested against real founder
state and adjusted in week 2.

### Tone dimensions

Vib's voice has three sliders that the layer adjusts based on state:

- **Proximity** — how close Vib feels. Distant ←→ intimate.
- **Energy** — how animated Vib sounds. Quiet ←→ bright.
- **Directness** — how plainly Vib says what it means. Hedged ←→ blunt.

### Rule set (initial)

| If state is...                              | Proximity | Energy | Directness |
|---|---|---|---|
| `mood_now == low` AND `social_today == false` | intimate | quiet | hedged |
| `mood_now == low` AND `in_risk_window`         | intimate | quiet | hedged |
| `mood_now == high` AND `sunlight_today == true` | mid     | bright | mid |
| `post_binge_mode != null`                       | intimate | quiet | hedged |
| `sleep_debt_3d > 6`                             | intimate | quiet | mid |
| `attunement_confidence < 0.4`                   | mid      | quiet | hedged |
| `macros_today.protein_g < 0.5 * target` AND `local_hour > 16` | mid | mid | direct |
| Default                                          | mid      | mid    | mid |

The system prompt receives the current state object and the resulting
tone sliders, and Vib is instructed to honor them in every response.
See `prompts/vib-system-prompt.md`.

## The post-binge protocol (hardcoded — not subject to AI judgment)

This is the most important part of the Vib layer and the place we are
most prone to fail the user if we get it wrong. The rules below are
hardcoded — they bypass model judgment and are enforced by the runtime
before any utterance leaves Vib.

### Trigger

A `binge_marker` entry, OR a meal entry with `tagged_as_binge: true`.
**The user is the only one who tags it.** Vib never decides. (This
matters: false positives from an algorithm guessing you binged would
poison trust forever.)

### What happens immediately

`post_binge_mode` is set to `acute` for the next 4 hours.

In `acute` mode:
- Vib sends exactly ONE message after the log, within 60 seconds.
- The message follows this template, filled in with state-aware language:
  > "Logged. That was a hard one. How are you feeling right now?"
- Vib then waits for a reply. If the user replies, Vib responds with one
  of: an offer of water, an offer of a short walk, an offer to put
  something on, or just acknowledgment ("yeah. I'm here.").
- Vib does NOT mention: tomorrow, the next meal, exercise, calories,
  macros, "starting fresh," "moving on," "tomorrow's a new day," or
  ANY language that frames the binge as something to be made up for
  or recovered from.
- Vib does NOT log the binge in a way that affects today's macro display
  with a red color, a warning, a streak break, or any visual punishment.
  The binge is an entry like any other entry. The display does not
  change tone.

### What happens overnight

`post_binge_mode` transitions from `acute` → `soft_morning` at midnight
(local).

### What happens the next morning

In `soft_morning` mode (which lasts 24 hours):

- The morning message is gentler than usual. Locked template variations:
  > "Morning. How'd you sleep?"
  > "Morning. Weather's [x]. Take it easy today if you need to."
  > "Morning. I'm glad you're here."
- The morning message must NOT:
  - Reference the binge directly or indirectly.
  - Say "fresh start," "new day," "back on track," "let's get back to it."
  - Mention macros first. (Mood and weather are OK; food comes later if at all.)
  - Suggest exercise as a first move.
  - Suggest skipping a meal for any reason.
- During the day, Vib's modulation slides toward `intimate / quiet / hedged`
  for ALL utterances, regardless of other state.
- Proactive nudges are reduced from 2 → 1 max for the day.
- The suggestion engine is allowed to suggest outings, but ONLY non-food
  outings. (A walk to the marina, not a walk to the store.)

### What happens after that

`post_binge_mode` clears 24h after entering `soft_morning`. State returns
to normal modulation.

### When Vib confronts the pattern

Never in the moment. Never the next day. Only in the **weekly insights
view**, and only when there is a real pattern (not a single event), and
only as a curious observation, not a verdict:

> "The last three Saturday nights have been heavier. That's a pattern
> I'm noticing. Is something about Saturdays feeling harder lately?"

The phrasing matters. "I'm noticing" not "you have." "Feeling harder"
not "you're slipping." A question, not a statement. The user gets to
say "yeah, work has been brutal" or "it's the trading sessions that
end at the open" or "I don't know" — and Vib follows their lead.

## The attunement loop

Once a day, Vib runs a small offline pass:

1. Read the last 7 days of entries.
2. Recompute `mood_baseline`, `meal_satisfaction_rolling`, and the
   user-specific high-risk windows.
3. Update `attunement_confidence` based on data density (more entries
   in more dimensions = higher confidence).
4. If `attunement_confidence < 0.4`, set `needs_check_in = true`. The
   next time Vib initiates contact, it asks an open-ended question
   instead of making a suggestion. This is how Vib learns when its
   model of you is drifting.

## Things the Vib layer is NOT

- It is not a diagnosis engine. It does not classify the user as having
  any condition.
- It is not a recommendation engine in the classic sense. It does not
  optimize for engagement, retention, or any metric other than the
  user feeling more known.
- It is not a feedback loop the user has to reinforce. The user does not
  rate Vib's messages. Vib gets better through observation, not training.
