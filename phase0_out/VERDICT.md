# Phase 0 Gate — Verdict

**Date:** 2026-07-06
**Model:** qwen3.5:9b (local Ollama, strictly offline)
**Result: NO-GO.** Discovery does not yet clear the Phase 0 bar. Do **not** build the
downstream agents (Analyst → Principal) until a revised Discovery passes this gate.

## Numbers (pre-committed criteria)

| Scenario | auto_pass | coverage | connected | grounded | grain_ok | orphans | turns | secs |
|---|---|---|---|---|---|---|---|---|
| vague_baker | ❌ | 0.00 | ❌ | ✅ | ❌ | 6 | 25 | 192 |
| rambling_agency | ❌ | 0.00 | ❌ | ✅ | ❌ | 1 | 25 | 191 |
| jargon_manufacturer | ❌ | 0.00 | ❌ | ✅ | ❌ | 3 | 25 | 159 |
| defensive_founder | ❌ | 0.00 | ❌ | ✅ | ❌ | 6 | 25 | 165 |

- **auto_pass_rate: 0/4. avg_coverage: 0.00. avg ~176 s/interview** (~$0 — local).
- All four ran the full 25-turn cap; none completed via the coverage target.

## What worked (do not rebuild)

- The infrastructure is sound: the offline loop runs, the eval harness drives Discovery
  against simulated hard clients, scoring fires, and **the gate itself correctly caught the
  failure before we built on it** — the whole point of Phase 0.
- **`grounded=True` on all four:** the evidence-required rule holds end-to-end. No
  hallucinated, unquoted nodes survived.
- The interviewer's *questions* are good: grounded in the client's own words,
  non-therapeutic, and adaptive (confirmed by reading transcripts).

## Root cause (this is the fixable part)

Coverage is **exactly 0.00 on all four**, which is a structural signature, not model
weakness. Inspecting the graphs:

1. **Steps are conversational fragments, not activities.** e.g. `vague_baker` produced 36
   "steps" with labels like *"hoping someone actually ordered scones"* and a full run-on
   sentence. → `grain_ok=False`.
2. **No node canonicalization.** Every rephrasing of the same activity becomes a *new*
   node (label dedup is exact-match; the model never repeats a label), so a single canonical
   step never accumulates its facets.
3. **Facet edges are sparse and scattered.** In `vague_baker`: 36 steps but only 1
   `produces` and 5 `uses` edges. No step ever gets actor + tool + (input|output) together
   → coverage 0.00.

**This is a Discovery extraction-prompt + node-identity problem — exactly the §4
"Discovery robustness" risk every design review flagged as the linchpin.** It is NOT
evidence that local models can't do this: the model engaged, grounded every claim, and
asked good questions. It was never *constrained* to extract a small set of canonical,
deduplicated, edge-complete steps.

## Chosen failure branch (pre-committed in the spec §8)

**"Change the approach" → iterate Discovery, do not proceed downstream.** Specifically, a
Discovery v2 that targets the three root causes:

1. **Extraction prompt:** demand a *small* set of canonical steps; each step a short
   verb-object label (≤ 5 words); for every step, explicitly emit who/tool/input/output
   edges in the same turn. Forbid extracting feelings/asides/run-ons as steps.
2. **Node canonicalization:** fuzzy-match new nodes to existing ones (normalize, stem,
   embed-or-alias) before creating, so the same activity consolidates instead of forking.
3. **Grain enforcement at write time:** reject/split step labels that trip the grain rule
   rather than only reporting them.

Then re-run this exact gate. The bar and scenarios are unchanged (fixed before the run, per
the anti-confirmation discipline) — Discovery v2 has to clear the same test.

## Bottom line

The gate worked. It converted "will Discovery hold up?" from an assumption into a measured
**no — not yet**, and localized the failure to the extraction prompt / node identity rather
than the model or the architecture. This is the cheapest possible place to have learned it:
before a single downstream agent was built on a broken map.
