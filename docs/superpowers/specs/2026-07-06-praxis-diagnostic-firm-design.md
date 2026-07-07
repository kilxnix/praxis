# Praxis — The Diagnostic Firm (Sub-project 1)

**Date:** 2026-07-06
**Status:** Design approved, pending spec review
**Codename:** Praxis (placeholder — "putting theory into practice")

---

## 1. What we're building

Praxis is an **offline, self-running "AI-implementation consultancy"** — a swarm of
autonomous agents that together behave like a real firm. You hand it a company's
current workflow; it studies that workflow and hands back a sharp, decision-ready
plan for enhancing it with AI.

This is a **repurpose of an existing offline agent engine**, not a greenfield build.
The current repository is *Vib*, a wellness companion (itself the result of a chain of
pivots: idea engine → Tamagotchi → dating → wellness). The durable core across all of
those is a **person-modeling engine**: a multi-agent orchestrator over a shared,
evidence-grounded state, running fully offline on local Ollama models. Praxis keeps
that spine and swaps the domain from *modeling a person* to *modeling a business
workflow*.

### Scope: this is Sub-project 1 of two

The full vision spans two very different difficulty levels. They are split, and **SP1
is built first and fully** before SP2 is specified — because SP2 literally consumes
SP1's output.

- **Sub-project 1 — The Diagnostic Firm (THIS SPEC).** Intake interview → build a model
  of the company's workflow → the full firm analyzes it → produces the deliverable (the
  AI-intervention design + rollout plan). Coherent, buildable, testable, and valuable on
  its own.
- **Sub-project 2 — The Build Wing.** Takes SP1's prioritized interventions and generates
  *actual runnable automation* that plugs into the client's tools. Now designed — see
  `2026-07-06-praxis-build-wing-design.md`. Implementation is gated on SP1 existing and
  stabilizing first.

---

## 2. Product decisions (locked)

These were decided during brainstorming and are load-bearing.

| # | Decision | Choice |
|---|---|---|
| 1 | **Output** | Both, in sequence: a consulting deliverable first, then (SP2) the built automation. Praxis (SP1) produces the deliverable. |
| 2 | **Intake** | Hybrid: interview-led, with optional document/artifact ingestion to ground the interview. |
| 3 | **Tone** | Personable, sharp, like a real consultant/operator in the room. **Explicitly NOT therapeutic** — a deliberate break from the wellness voice. No soft mirroring, no "how does that make you feel." |
| 4 | **The firm** | Full firm: a **Principal** conductor + 5 specialists (Discovery, Analyst, Architect, Business-case, Skeptic), waking only who's needed. |
| 5 | **Models / offline** | **Strictly offline, local-only.** Everything runs on local Ollama. No client data ever leaves the machine. |
| 6 | **Autonomy** | **Fire-and-forget.** The interview is the only interactive part; once Discovery has enough, the firm runs to completion and presents the finished package. |
| 7 | **The gate** | Because the human is no longer the approval gate, the **Skeptic agent is the gate** — it pressure-tests the diagnosis before sign-off and can send work back for a redo. |
| 8 | **Code location** | Fresh `praxis/` package with honestly-named modules, reusing patterns/code from `interviewer/`; then delete `interviewer/`. |

### The Ocean Principle (governing constraint)

> **We are the ocean; the business is the boat. We adapt to them; they never adapt to us.**

No canned templates, no forcing a client's reality into our categories. Every engagement
is shaped around how *this* business actually works, in *its own* language. This
principle has teeth in the design: it dictates the Workflow Model's shape (Section 4),
and the Skeptic actively guards it (Section 5) as an explicit sign-off check.

---

## 3. Architecture — blackboard + conductor

All agents read from and write to one shared **EngagementState** (the Workflow Model plus
findings-so-far). A **Principal** conductor decides who runs next; the **Skeptic** can
trigger a revision loop before sign-off. Specialists never message each other directly —
they communicate *through the shared state*. This keeps the system flexible (a real firm
loops when the analysis is weak) while staying testable and offline-reliable (state is
explicit and inspectable).

This maps directly onto the existing `orchestrator.py`, which already conducts turns over
a shared state (the `ConversationGraph`). We keep the spine and swap what the state holds.

### Run lifecycle

```
1. INTAKE      Discovery interviews you (+ ingests any docs) -> grows Workflow Model
2. DIAGNOSE    Analyst finds friction points & AI-opportunity points
3. DESIGN      Architect designs each AI intervention
4. JUSTIFY     Business-case scores each intervention (effort, time saved, risk)
5. CHALLENGE   Skeptic pressure-tests everything -> can bounce steps 2-4 for a redo
6. SYNTHESIZE  Principal assembles the deliverable and presents it
```

- **Step 1 is the only interactive part.** It ends when the Workflow Model reaches
  sufficient confidence (Section 4).
- **Steps 2–5 are the fire-and-forget autonomous stretch.**
- **Step 5 (Skeptic) is the internal gate** that replaces human approval.

---

## 4. The Workflow Model — emergent evidence-graph

The Ocean Principle rules out a fixed schema (predefined fields every workflow must fill —
that forces every boat into the same hull). Instead, the Discovery agent *grows* a graph
from the actual conversation, in the client's own words. Nothing about the structure is
predefined; it emerges from what they tell us.

This is a near-perfect reuse of the existing engine, which is already "evidence-first:
signals stored with the user's *actual quotes*," rebuilt into a graph on load.

**Nodes** (emergent, named in the client's vocabulary):
- **Steps / activities**
- **Actors** (roles or real people)
- **Tools / systems**
- **Artifacts** (the inputs & outputs that flow through the work)
- **Frictions** (pain, delay, rework)

**Edges:**
- `step → next step` (sequence)
- `actor → performs → step`
- `step → uses → tool`
- `step → produces / consumes → artifact`
- `step → causes → friction`

**Grounding & confidence:**
- Every node and edge carries **evidence** — the client's literal quote or a document
  excerpt — so nothing is invented. (Repurposes `trait_evidence` → `workflow_evidence`.)
- Every element carries a **confidence** score (repurposes the `DimensionConfidence`
  pattern). A vague area = low confidence = another Discovery follow-up. **This is how the
  firm knows intake is done:** the fire-and-forget stretch begins only when the map is
  solid.

**Discovery robustness (the highest-risk part of the system).** Building a coherent,
appropriately-granular graph from unstructured conversation is genuinely hard; if Discovery
produces a shallow, fragmented, or hallucinated map, every downstream agent operates on bad
data. The map is the foundation, so it gets explicit safeguards. Crucially, these are
**process scaffolding, not content templating** — the distinction that keeps them compatible
with the Ocean Principle:

- *Process scaffolding (allowed):* disciplined probing over the **universal structural
  primitives** the graph is already made of. For every Step, Discovery drives toward: who
  performs it, what tool it uses, what comes in, what goes out, what breaks. This asks
  *about their reality in their words*; it imposes no domain categories.
- *Content templating (forbidden):* predefined industry checklists or "typical workflow"
  templates the client's reality must be bent to fit. This is exactly what Ocean rules out.

Concretely, Discovery gets:
- **Coverage probes** — the who/tool/in/out/breaks sweep above, so steps don't end up as
  dangling nodes with no edges.
- **Granularity discipline** — model at a consistent grain: the **handoff between a person
  and a tool, or between two people**. Guards against one region mapped step-by-step and
  another as a single "the sales department does stuff" blob.
- **Thin-area flagging + push-harder** — when a region stays low-confidence, Discovery
  *names the gap out loud and probes it* rather than quietly moving on. Because intake is
  the only interactive window, this is where thin human answers get repaired — not
  downstream where they can't be.
- **Anti-hallucination rule** — a node/edge with no evidence quote is not allowed to exist.
  No evidence → it's a question to ask, not a fact to assert. (This makes "over-structured
  hallucination" mechanically hard: structure can't outrun grounding.)

**A known limit, stated plainly:** confidence scoring is only as good as the model's
calibration, and models are weak at knowing what they don't know. The safeguards above
(coverage sweep, grain discipline, evidence requirement) reduce reliance on raw
self-assessed confidence, but Discovery's prompt + stopping criteria are flagged as the
**first thing to prototype and iterate**, ahead of the rest of the firm — see §8.

**Reuse tally:** `ConversationGraph` → `EngagementState`, evidence-first storage →
`workflow_evidence`, `DimensionConfidence` → per-element confidence, phase progression →
intake-completeness. The orchestrator spine survives; the domain changes.

---

## 5. The firm roster — six brains on one blackboard

Each agent is its own brain: a distinct persona, its own system prompt, its own local
model, and a strict contract for what it reads from and writes to the EngagementState.
"Its own brain" is real, not cosmetic — reusing `persona_builder.py` + `prompt_builder.py`
+ `ModelTier`, each agent gets its own persona and can run a different local model (e.g., a
leaner model for Discovery's fast turns, a heavier local model for the Architect's
reasoning) — all still strictly offline.

| Agent | Its brain / voice | Reads | Writes |
|---|---|---|---|
| **Principal** | The partner in the room. Personable, sharp, plain-spoken — *not* therapeutic. Runs the engagement (who wakes next, when intake is done, when the Skeptic is satisfied) and delivers the final package in a human voice. | Everything | Conducting decisions + final deliverable |
| **Discovery** | Curious operator who's "walked a hundred shop floors." Conducts the intake interview, ingests dropped docs, grows the Workflow Model, stops when confidence is high enough. | Transcript, docs | Workflow Model nodes/edges + evidence + confidence |
| **Analyst** | Pattern-hunter. Reads the finished map and marks friction points and AI-opportunity points — specific to *this* workflow, never a checklist. | Workflow Model | Opportunity nodes (each tied to evidence) |
| **Architect** | Systems designer. For each opportunity, designs the concrete AI intervention — what it does, where it plugs in, what it needs. | Opportunities + Workflow Model | Intervention designs |
| **Business-case** | Numbers/feasibility voice. Scores each intervention: effort to adopt, time/cost saved, risk, disruptiveness to the boat. | Interventions | Scores + prioritization |
| **Skeptic** | The internal gate. Pressure-tests the whole chain (grounded in evidence? will it actually work for them? **are we adapting to them or forcing them to adapt to us?**). Can bounce Analyst/Architect/Business-case for a redo; signs off only when it holds. | Everything | Verdicts, redo-requests, sign-off |

**The Skeptic enforces the Ocean Principle.** One of its explicit sign-off checks is "are
we adapting to them, or making them adapt to us?" — so the principle is actively guarded by
an agent before anything ships.

**The Skeptic is the make-or-break agent, and its failure modes are asymmetric** — too
lenient ships slop, too strict burns expensive redo loops on local models. Three design
rules keep it honest without letting it thrash:

1. **It runs the heaviest local model** (the top `ModelTier`) and gets the most careful
   prompt of the six. It is the quality gate; it is not the place to economize.
2. **Its checklist is concrete and falsifiable**, not "be critical": *is every claim backed
   by an evidence quote? does any intervention create more friction than it removes? are we
   forcing the boat to fit us? is the map deep enough to justify this recommendation?*
3. **Redo requests must be specific and addressable** ("intervention #3 assumes a CRM the
   evidence never mentions"), and **the loop is bounded** — after a capped number of redo
   rounds (config, default 2), the Skeptic stops looping and instead **ships the deliverable
   with its unresolved objections attached as flagged caveats.** A capped loop that
   degrades to honest caveats beats an unbounded loop that stalls the run.

---

## 6. The deliverable — what the Principal hands you

Two layers: a **structured data layer underneath** (JSON — so SP2's Build Wing can later
consume it directly) and a **human presentation on top** (rendered in the existing FastAPI
+ `static/` browser UI, so it reads like a real firm's output). Plus an easy **export**
(Markdown/PDF) for sharing — trivial once the structured artifact exists.

**Contents — shaped by the Ocean Principle, told in the client's own language:**

1. **"Here's your workflow, as we heard it."** The mapped Workflow Model played back in
   *their* words, grounded in their own quotes. The trust move: prove we understood the
   boat before recommending anything. **Regions we couldn't map confidently are shown as
   such** ("we didn't get a clear picture of how X hands off to Y") rather than papered
   over — honest gaps beat confident fiction, and they tell the client exactly where a
   follow-up would sharpen the plan.
2. **Where it hurts.** The friction points, each tied to the evidence that surfaced it.
3. **Where AI fits.** The prioritized interventions. Each: *what it does · where it plugs
   into the existing flow · what changes for the people doing the work · effort to adopt ·
   time/cost saved · risk.*
4. **The rollout.** A sequenced plan — quick wins first, bigger bets after — so they can
   start Monday, not drown in a transformation.
5. **What we're NOT recommending, and why.** The honesty section. Where AI doesn't help,
   we say so — plus any **unresolved Skeptic objections** carried over from a capped redo
   loop (§5). This is the credibility feature — the difference between helping companies
   *actually implement* AI and selling hype.

**Actionable on its own.** Every intervention is written so a human on the client's side
could act on it *without* the Build Wing (SP2) — the rollout's quick wins are things
someone could start Monday by hand. SP1's value is therefore not hostage to SP2 shipping;
SP2 automates what SP1 already makes actionable. (This is a deliberate answer to "a
diagnosis nobody acts on" — see §8.)

**Format:** structured JSON + browser render, with Markdown/PDF export as an easy add-on.

---

## 7. Persistence, testing, tech

**Tech stack — unchanged:** Python / FastAPI / Uvicorn, Ollama local models, SQLite,
vanilla-JS frontend. Strictly offline throughout.

**Keep & adapt (proven spine):** the orchestrator's turn-conducting loop, evidence-first
storage, `prompt_builder` / `persona_builder`, `ModelTier` routing, confidence-gating.

**Retire (wellness/dating-specific):** the `vib_wellness/` package (post-binge protocol,
meal/mood logging), wellness entry tables (`entries`, `vib_state`, `risk_windows`,
`nudges`), the food-vision tier, and the personality/wellness dimension sets.

**Persistence — repurposed DB** (`souls.db` → `praxis.db`):

| Old (person-modeling) | New (workflow-modeling) |
|---|---|
| `souls` | `engagements` (one per company/workflow studied) |
| `sessions` / `messages` | intake sessions / interview transcript |
| `trait_evidence` | `workflow_evidence` (client's literal quotes / doc excerpts) |
| `soul_state` cache | `engagement_state` cache |
| *new* | `workflow_nodes`, `workflow_edges`, `opportunities`, `interventions`, `deliverable` (JSON) |

**Code location:** fresh `praxis/` package with honest names (`principal.py`,
`discovery.py`, `firm.py`, `engagement.py`, etc.), reusing patterns/code from
`interviewer/`; then delete `interviewer/`. The person→workflow shift is total enough that
clean naming pays for itself. **Avoid domain drag:** reuse *structural* code (orchestrator
loop, storage, confidence gating) freely, but **rewrite every prompt and persona from
scratch** for the workflow domain. The wellness prompts were shaped by modeling people
(emotions, habits, states over time); workflow modeling has different structure and
different failure modes. Find-replacing the old prompts would smuggle in assumptions that
don't translate.

**Testing** (same pytest harness: `.venv\Scripts\python.exe -m pytest tests/ -v`). Two
layers, because "did it run" and "was the diagnosis any good" are different questions:

- **Mechanical (deterministic, in CI):** each agent is unit-testable in isolation against a
  faked EngagementState. The integration tests that matter: *(a)* intake grows the graph
  and stops at high confidence; *(b)* the Skeptic's redo-loop bounces weak work, then either
  signs off or hits the cap and ships with caveats; *(c)* the anti-hallucination rule holds
  — no evidence-less nodes survive.
- **Quality (golden fixtures + human rubric):** a small set of **golden engagements** —
  canned interview transcripts with a known-good expected graph *shape* and expected
  opportunity *themes* — so a regression in Discovery or the Analyst is caught structurally.
  Actual deliverable quality ("would this help a real company?") is **genuinely subjective
  and not fully automatable**; we score it with a **human-review rubric** (evidence-grounded?
  adapted to them? actionable? honest about gaps?), not a faked automated oracle. Pretending
  we can auto-grade advice quality would be the more dangerous mistake.

---

## 8. Design-review responses: risks, mitigations, and where we hold the line

A design review (2026-07-06) stress-tested this spec. The substantive risks and how the
design answers them:

| Risk raised | Response |
|---|---|
| **Emergent graph is the weakest link; everything depends on it.** | Agreed — the top risk. Addressed with the Discovery safeguards in §4 (process scaffolding over universal primitives, coverage probes, grain discipline, evidence-required rule) and by making **Discovery's prompt + stopping criteria the first thing prototyped**, ahead of the rest of the firm. |
| **Skeptic is hard to tune; failure modes are asymmetric.** | Agreed — §5 gives it the heaviest model, a concrete falsifiable checklist, specific redo requests, and a **bounded loop that degrades to honest caveats** rather than thrashing. |
| **System is brittle to shallow interview answers.** | Agreed — §4 thin-area flagging repairs gaps *during* the interactive window; §6 marks what couldn't be mapped rather than faking it. |
| **Testing is too light for a subjective-quality task.** | Agreed and scoped — §7 adds golden-fixture engagements + a human-review rubric, and explicitly refuses to fake an automated quality oracle. |
| **Six-agent overhead may not beat fewer, stronger agents.** | **Partial pushback.** The full firm is a deliberate product decision ("embodiment of a firm"), not incidental, and the design already mitigates cost: the conductor wakes only who's needed, and agents can share one local model. **Fallback if latency proves prohibitive in practice:** merge adjacent specialists (e.g. Analyst+Architect) — an implementation-time optimization, not a design change. We do not collapse the roster preemptively. |
| **Repurposing person-modeling code causes domain drag.** | Agreed, cheaply — §7 keeps structural code but **rewrites all prompts/personas from scratch** for the workflow domain. |
| **May solve the wrong bottleneck — a diagnosis nobody acts on.** | Mostly already answered: SP2 *is* the implementation half, and §6 makes SP1's deliverable **human-actionable on its own** so its value isn't hostage to SP2. |

**The one thing worth de-risking before full build:** the reviewer's sharpest point is that
the emergent graph + confidence mechanism is the linchpin. So the implementation plan should
**prototype Discovery first** — prove it can build a solid, grounded, appropriately-grained
map from a real conversation — before investing in the five downstream agents that all depend
on it.

---

## 9. Open questions (deferred, not blocking)

- **Product name.** "Praxis" is a placeholder.
- **Architect's recommendation bias.** Praxis itself runs strictly offline, but the AI
  solutions it *recommends to a client* aren't inherently constrained to offline/local.
  Whether the Architect should lean toward privacy-preserving local solutions is a tunable
  preference, deferred to implementation.
- **Document ingestion depth.** SP1 assumes text docs (SOPs, transcripts). Screenshot/
  image ingestion (which could revive a vision tier) is deferred.
- **All of Sub-project 2** (the Build Wing) — out of scope until this stabilizes.
