# Phase 0 Gate — Discovery v2 Verdict

**Date:** 2026-07-06
**Model:** qwen3.5:9b (local Ollama, strictly offline)
**Result: still NO-GO — but decisive, measured progress.** Do not build downstream
agents yet. The next branch is **semantic dedup** (pre-committed in the v2 spec §F2 / plan
Task 5), not more hand-plays.

## Numbers vs v1 (same scenarios, same bar, fixed before the run)

| metric | v1 | v2 |
|---|---|---|
| avg coverage | 0.00 | **0.22** |
| grain_ok | ❌ all four | **✅ all four** |
| orphans (per scenario) | 1–6 | 1–2 |
| auto_pass_rate | 0/4 | 0/4 |

| Scenario | coverage | connected | grain_ok | orphans | turns |
|---|---|---|---|---|---|
| vague_baker | 0.19 | ❌ | ✅ | 2 | 25 |
| rambling_agency | 0.25 | ❌ | ✅ | 1 | 25 |
| jargon_manufacturer | 0.12 | ❌ | ✅ | 2 | 25 |
| defensive_founder | 0.31 | ❌ | ✅ | 2 | 25 |

## What v2 fixed (confirmed working)

- **Grain guard: solved.** Step labels are now short verb-object phrases
  ("answer phone", "grab traveler from bin", "scribble number") — `grain_ok=True`
  everywhere, versus sentence-fragments in v1. `is_valid_step_label` + the rewritten
  extraction prompt work.
- **Surface dedup: working.** `canonical_label` collapses article/case/punctuation
  variants; the edge-path grain bypass is closed so fragments can't re-enter.
- **Coverage moved off zero (0.00 → 0.22).** The plays engine + same-turn facet-edge
  prompt do accumulate facets — one step per scenario reaches full satisfaction
  (e.g. `estimate remaining stock`: actor+tool+input+output).

## What still blocks the gate (the v3 target)

**Semantic step duplication — the piece deliberately deferred in v2.** `canonical_label`
only normalizes surface form, so tense/plural/synonym variants of the SAME activity survive
as separate step nodes:
- `vague_baker`: `scribble number` / `scribble numbers` / `scribbling numbers` /
  `write five dots` / `scribble five dots` / `mark dots in notebook` — six-plus nodes for
  one activity (recording the order).
- `jargon_manufacturer`: `logs roughing hours` / `hit pause to log hours` /
  `scribbling setup times onto traveler` — overlapping duplicates.

Because one real step is split across many nodes, its facet edges scatter and no single node
reaches actor+tool+(input|output). This is *the* reason coverage plateaus at ~0.22 and the
graph stays disconnected (leftover orphan steps that never got facet-completed).

## Chosen next branch (pre-committed): semantic dedup (Discovery v3)

The v2 spec/plan pre-committed this exact branch. Two tiers, cheapest first:

1. **Cheap: lemmatize/stem in `canonical_label`.** Normalize verb tense and noun plurals
   (and spelled-out numbers) so `scribble number` = `scribble numbers` = `scribbling
   numbers`. This alone should merge a large fraction of the duplicates with no new
   dependency and no LLM call — still fully deterministic and Ocean-safe.
2. **If still short: semantic merge.** A cheap local-embedding or a targeted LLM
   "same step? yes/no" adjudication pass to merge `write five dots` ≈ `scribble five dots`
   (different verbs, same activity). Ocean-safe (operates on the client's own labels; imposes
   no external categories).

Then re-run this same gate. Expected effect: consolidating ~16 fragmented steps into ~5 real
ones lets the same 25 turns complete their facets, which should move coverage toward the 0.8
bar and connect the graph.

## Bottom line

v2 is not a failure — it's the gate working as designed: it converted "did the plays engine
+ grain guard help?" into a measured **yes (0→0.22, grain solved)**, and localized the
remaining blocker to one precise, pre-anticipated cause (semantic duplication). The path to a
passing Discovery is now narrow and concrete, not speculative.
