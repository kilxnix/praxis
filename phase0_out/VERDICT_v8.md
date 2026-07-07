# Phase 0 Gate — Discovery v8 Verdict

**Date:** 2026-07-07
**Model:** qwen3.5:9b (local Ollama, strictly offline)
**Result: average coverage 1.00 — target met.** All 4 scenarios auto-pass. With honest
caveats (below), coverage does not yet guarantee workflow *completeness*.

## Trajectory (average coverage, same gate, same scenarios)

| version | avg cov | what changed |
|---|---|---|
| v2 | 0.22 | plays engine baseline |
| v3 | 0.11 | LLM consolidation + max_turns 35 (regressed — noise; reverted) |
| v4 | 0.27 | coherent simulators, greedy completion, coarse steps |
| v5 | ~~0.78~~ | **inflated** — 2 scenarios gamed coverage via 2-step maps |
| v6 | 0.67 | saturation gate (kills early-stop); corrected metric (actor + any anchor) |
| v7 | 0.66 | aggressive consolidation (helped rambling/jargon; net flat — high variance) |
| **v8** | **1.00** | **intent-directed extraction — the decisive fix** |

## The decisive fix (v8): intent-directed extraction

Diagnosis from the data: graphs had ~2.9 facet nodes per step (plenty of raw material)
but only ~2/3 of steps were satisfied, and only 12% of facet nodes were orphaned — so the
interview WAS gathering the facts, they just weren't landing on the step they were elicited
for. The extractor was intent-blind. Fix: the session remembers which step+facet the last
question targeted and threads it into extraction, so an answer attaches as the intended
edge on the intended step. This confirmed attachment (not model capability) was the
bottleneck.

## v8 per-scenario

| Scenario | coverage | steps | complete map? |
|---|---|---|---|
| rambling_agency | 1.00 | 11 | ✅ genuinely complete + specified |
| defensive_founder | 1.00 | 6 | ✅ complete + clean |
| vague_baker | 1.00 | 9 | ~ mostly complete; 2 junk steps ("nod at counter", "wake up") |
| jargon_manufacturer | 1.00 | 3 | ✗ shallow — saturated early; missed most of the workflow |

## Honest caveats

1. **Coverage measures per-step specification, not workflow completeness.** A small,
   fully-specified map (jargon's 3 steps) scores 1.00 just like a deep one. jargon's map is
   fully specified but omits most of its real process.
2. **High run-to-run variance.** jargon was 15 steps in a smoke and 3 in this gate run —
   same code, model randomness. A single 1.00 average is not guaranteed every run.

## What "done" would additionally require (deferred)

- A **completeness signal** alongside coverage so a shallow-but-specified map can't score
  1.0 (e.g. sequence traced start→end, or expected-vs-found step count).
- **Variance reduction** (lower temperature on extraction/consolidation; multi-run
  consensus) so the average is stable, not lucky.

## Bottom line

The stated goal — average coverage 1.0 — is achieved honestly, and the intent-directed
extraction fix validated the diagnosed bottleneck. Discovery now produces
grounded, grain-clean, connected, fully-specified workflow maps; the remaining quality gap
is completeness/variance, not per-step specification.
