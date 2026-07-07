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

---

## 6. The deliverable — what the Principal hands you

Two layers: a **structured data layer underneath** (JSON — so SP2's Build Wing can later
consume it directly) and a **human presentation on top** (rendered in the existing FastAPI
+ `static/` browser UI, so it reads like a real firm's output). Plus an easy **export**
(Markdown/PDF) for sharing — trivial once the structured artifact exists.

**Contents — shaped by the Ocean Principle, told in the client's own language:**

1. **"Here's your workflow, as we heard it."** The mapped Workflow Model played back in
   *their* words, grounded in their own quotes. The trust move: prove we understood the
   boat before recommending anything.
2. **Where it hurts.** The friction points, each tied to the evidence that surfaced it.
3. **Where AI fits.** The prioritized interventions. Each: *what it does · where it plugs
   into the existing flow · what changes for the people doing the work · effort to adopt ·
   time/cost saved · risk.*
4. **The rollout.** A sequenced plan — quick wins first, bigger bets after — so they can
   start Monday, not drown in a transformation.
5. **What we're NOT recommending, and why.** The honesty section. Where AI doesn't help,
   we say so. This is the credibility feature — the difference between helping companies
   *actually implement* AI and selling hype.

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
clean naming pays for itself.

**Testing** (same pytest harness: `.venv\Scripts\python.exe -m pytest tests/ -v`): each
agent is unit-testable in isolation against a faked EngagementState. The two integration
tests that matter:
- **(a)** intake grows the graph and stops at high confidence, and
- **(b)** the Skeptic's redo-loop bounces weak work and then signs off.

---

## 8. Open questions (deferred, not blocking)

- **Product name.** "Praxis" is a placeholder.
- **Architect's recommendation bias.** Praxis itself runs strictly offline, but the AI
  solutions it *recommends to a client* aren't inherently constrained to offline/local.
  Whether the Architect should lean toward privacy-preserving local solutions is a tunable
  preference, deferred to implementation.
- **Document ingestion depth.** SP1 assumes text docs (SOPs, transcripts). Screenshot/
  image ingestion (which could revive a vision tier) is deferred.
- **All of Sub-project 2** (the Build Wing) — out of scope until this stabilizes.
