# Discovery v2 — The Plays-Engine

**Date:** 2026-07-06
**Status:** Design approved, pending spec review
**Follows:** Phase 0 gate NO-GO (`phase0_out/VERDICT.md`) — Discovery v1 scored 0/4, coverage 0.00.
**Part of:** Praxis SP1 (`2026-07-06-praxis-diagnostic-firm-design.md`), the Discovery agent.

---

## 1. Why

The Phase 0 gate failed: Discovery v1 built fragmented, un-consolidated graphs — 36
sentence-fragment "steps" per interview, near-zero facet edges, so no step ever reached
actor + tool + (input|output) and coverage was exactly 0.00 on all four scenarios.
`grounded=True` everywhere confirmed the pipeline, offline loop, evidence rule, scoring,
and gate all work — the failure is localized to Discovery's **extraction strategy and
question selection**.

v2 fixes that, and does so via an architecture (explicit "plays") that doubles as the
substrate for a later self-improving interviewer. It is the first real brick of the
"learns to interview better over time" vision — built with hand-authored plays now, so the
learning loop (Phase B, out of scope here) plugs in later with no rework.

**Governing constraint (unchanged): the Ocean Principle.** Every play is about *interview
dynamics*, never about businesses. No play, signal, or heuristic may encode domain content
(no "bakeries use notebooks"). Cross-engagement learning of *client content* is forbidden;
only *interviewing skill* may ever be learned. This is enforced mechanically where possible
(§6) and by review always.

---

## 2. Architecture — the plays-engine

The interviewer's move each turn is decided by a small registry of content-free **plays**.

- **`Play`** = `{id: str, kind: "question" | "consolidate", priority: int, matches(state) ->
  bool, focus(state) -> str}`.
- **`InterviewState`** (what plays see) = the `WorkflowModel`, its `CoverageReport`, and
  cheap deterministic **answer-signals** about the last client turn (vagueness, novelty).
- **The engine**: each turn, evaluate every play's `matches(state)`, pick the
  highest-`priority` match, and use its `focus(state)` string as the directive handed to the
  existing `next_question`. `consolidate` plays instead run a graph transform before the
  question is chosen.

This generalizes v1's single hard-coded `focus_hint_for` into an ordered, extensible,
testable registry. The existing pipeline is otherwise preserved: `extract_deltas` →
normalize/dedup → `apply_deltas` → coverage → **plays-engine** → `next_question` → session
loop.

---

## 3. The three gate failures, each fixed concretely

**F1 — fragment steps (grain).**
- Deterministic `is_valid_step_label(raw) -> bool`: rejects labels that are >5 words,
  contain hedge/feeling words (`hoping`, `maybe`, `because`, `wish`, `hope`, `guess`), are
  phrased as a question, or are first-person feelings. Used as a write-time backstop in
  extraction: an `add_node` step delta failing the guard is dropped (it will be re-elicited
  by a play).
- The extraction prompt is rewritten to demand short **verb-object** step labels.

**F2 — no canonicalization.**
- `canonical_label(raw) -> str`: lowercase, strip leading articles (`the/a/my/our/your`),
  strip filler, collapse whitespace. Node identity (`find_node` / `_get_or_add`) matches on
  the canonical form, so "the notebook" / "my notebook" / "notebook" collapse to one node
  and its facet edges accumulate instead of forking.
- *Out of scope for v2 (YAGNI):* semantic dedup ("memory" ≈ "count on fingers"). Surface
  canonicalization handles the bulk of the fragmentation; semantic merging waits until the
  gate shows it's the remaining blocker.

**F3 — sparse facet edges → coverage 0.00.**
- The extraction prompt requires that when a step is described, its who/tool/input/output
  edges are emitted **in the same turn**.
- The `complete_step_facets` play relentlessly targets the specific missing facet of a
  step, turn after turn, until steps are complete.

---

## 4. Answer-signals (the Ocean-safe home for the regex instinct)

Plays trigger partly on cheap deterministic reads of the last client answer — this is where
pattern/regex logic lives, kept strictly content-free:

- `is_vague(answer) -> bool`: short length AND/OR presence of hedge words — a read of
  *conversational dynamics*, not meaning.
- `introduces_novelty(answer, model) -> bool`: the answer contains substantive tokens not
  yet present in the graph's evidence — signals there's a new thread to chase.

Explicitly **not** allowed: any signal that classifies content ("this names a *tool*",
"this is an *invoicing* step"). Node typing is the LLM's job via extraction; the
deterministic layer only measures form, never domain.

---

## 5. Seed plays (hand-written, content-free)

Ordered by priority (high → low); the engine fires the highest match.

| Play | `kind` | Fires when | `focus` / action |
|---|---|---|---|
| `establish_first_step` | question | graph has no steps | ask them to name the very first thing that happens |
| `consolidate_similar` | consolidate | ≥2 steps share actor+tool, or have canonical-equal labels | merge via canonicalization, then a confirming question |
| `complete_step_facets` | question | some step is missing actor/tool/input/output | ask that specific missing facet for that step |
| `probe_after_vague` | question | last answer `is_vague` | ask for the most recent concrete instance, not a definition |
| `trace_sequence` | question | ≥1 step, few `sequence` edges | ask what happens right after the last known step |
| `surface_friction` | question | structure complete on a step, no friction noted | ask what usually goes wrong there (deliberately last) |

`surface_friction` is lowest priority so friction is probed only after structure exists
(consistent with the Phase 0 friction-carve-out decision). **Completion is not a play** —
the session's `is_intake_complete` (coverage target AND ≥2 steps, or the turn cap) still
owns stopping, and it is checked *before* the engine is consulted, so a covered interview
closes before any play fires. `select_play` always returns a play (the registry's fallback
is `complete_step_facets`, then `trace_sequence`) because it is only called mid-interview.

---

## 6. Ocean enforcement (mechanical + review)

- A unit test asserts each play's `focus`/directive text contains no hardcoded business
  nouns (a small denylist of domain words + a check that directives are templated on the
  client's own step labels, not canned content). **Honest limit:** this catches obvious
  leakage, not everything; the durable guard is that plays are authored about interview
  dynamics only, plus design review.
- The `Play` structure and registry are built so a future learning loop can *append/refine*
  plays — and any machine-proposed play must pass the same leakage test before entering the
  registry. That makes the Ocean guard a gate the learning loop cannot bypass.

---

## 7. Files

- `praxis/discovery_signals.py` — `canonical_label`, `is_valid_step_label`, `is_vague`,
  `introduces_novelty`. Pure, deterministic, unit-tested.
- `praxis/plays.py` — the `Play` dataclass, the seed registry, and `select_play(state) ->
  Play`.
- `praxis/discovery.py` — rewire `next_question` to consult `select_play`; apply
  `canonical_label` in `_get_or_add`; apply `is_valid_step_label` guard in extraction.
- `praxis/discovery_prompts.py` — rewritten extraction prompt (short verb-object steps +
  same-turn facet edges).
- `praxis/session.py` — run a `consolidate` play's transform when selected.
- Tests mirror each.

**Reuse, don't rebuild:** `models.py`, `coverage.py`, `llm_client.py`, the eval harness,
scoring, and the gate runner are unchanged. v2 touches only the extraction/questioning core.

---

## 8. Testing & the verdict

- **Unit:** `canonical_label` (variants collapse), `is_valid_step_label` (fragments
  rejected, good labels kept), `is_vague`/`introduces_novelty`, each play's `matches`/`focus`
  in isolation, `select_play` priority ordering, the Ocean leakage test, and dedup
  consolidation on `_get_or_add`.
- **Regression:** the existing 34 tests must stay green (or be updated where the extraction
  contract legitimately changed).
- **The verdict:** re-run the **same** Phase 0 gate — unchanged scenarios, unchanged bar
  (connected/grounded/grain_ok/coverage≥0.8), fixed before the run. Success = coverage
  moves decisively off 0.00 and a majority of scenarios auto-pass. If it still fails, the
  next branch is semantic dedup and/or a stronger extraction model — not more hand-plays.

---

## 9. Out of scope (deferred)

- **Phase B — the learning loop** (machine proposes/refines plays from gate feedback). v2
  is its substrate; the loop is a separate spec once v2 passes the gate.
- **Semantic dedup** (embedding/LLM alias merging) — added only if canonicalization proves
  insufficient at the gate.
- **Downstream agents** (Analyst → Principal) — still gated behind a passing Discovery.
