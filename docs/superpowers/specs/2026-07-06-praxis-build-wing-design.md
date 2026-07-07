# Praxis — The Build Wing (Sub-project 2)

**Date:** 2026-07-06
**Status:** Design approved, pending spec review
**Depends on:** Sub-project 1 — the Diagnostic Firm (`2026-07-06-praxis-diagnostic-firm-design.md`)

---

## 1. What we're building

The Build Wing is the second half of Praxis: it takes the prioritized interventions
produced by SP1 (the Diagnostic Firm) and **generates actual runnable automation** that
plugs into the client's real tools. It is a **continuation of the same engagement**, not a
separate application — it picks up the SP1 `EngagementState`, extends it with build
artifacts, and the whole thing flows intake → deliverable → build as one fire-and-forget
run that stops only at the airlock.

Architecturally it is a **compiler with pluggable backends**: an intervention design
compiles to a tool-agnostic intermediate representation (the BuildSpec / IR), and
per-intervention *generators* turn that IR into whatever the client's actual stack needs.

### Scope for v1

Per the sequencing decision (SP2 Q3), v1 builds the **full compiler front-end plus one
backend**, with the other backends as clean plug-ins added later:

- **Built now:** the IR, the Solutioner, the Verifier, the Integrator, the plug-in
  framework, the Tool Catalog, and the **Python-script generator** (the first backend).
- **Deferred plug-ins:** the n8n/visual-flow generator and the agent/prompt-package
  generator. They consume the *same* IR, which is exactly why we harden the IR against one
  real backend first.

---

## 2. Product decisions (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | **Output form** | Pluggable compiler (option D): intervention → tool-agnostic BuildSpec (IR) → per-intervention generator backend → artifact. |
| 2 | **Live-systems boundary** | Generate + sandbox-verify only. **A human deploys.** Praxis never touches production. |
| 3 | **v1 scope** | Full compiler front-end + **one** backend; other backends are later plug-ins. |
| 4 | **First backend** | The **Python-script generator** (most general → stress-tests the IR hardest; verifies cleanly in the existing pytest sandbox). |
| 5 | **Tool targeting** | Hybrid: curated offline **Tool Catalog** for common tools + **adapter stubs** for bespoke/unknown tools. |

### The Airlock Principle (governing constraint)

> **Praxis never touches the client's live systems or real credentials. It only ever
> produces sandbox-verified artifacts; a human carries them across the airlock into
> production.**

This is the SP2 counterpart to SP1's **Ocean Principle**, and both remain in force here:
we adapt to the boat's actual tools (Ocean), and we never point generated code at real
data ourselves (Airlock). The Airlock is enforced *mechanically* (sandbox isolation, no
network, no real credentials), not merely by convention.

---

## 3. The Build Wing — roster & pipeline

Same blackboard-and-conductor spine as SP1, same Principal conducting, same redo-loop
discipline. Four new brains extend the firm.

| Agent | Its job | Reads | Writes |
|---|---|---|---|
| **Solutioner** | The compiler front-end. Turns an approved SP1 intervention *design* into a precise, buildable **BuildSpec (IR)**: trigger, inputs (and their source tool), logic, outputs (and their destination tool), any model calls, success criteria, and **sample fixtures** to verify against. | Intervention designs + Workflow Model | BuildSpec (IR) |
| **Generator** *(v1: Python-script backend)* | Turns one BuildSpec into a real artifact — code + config + its own tests. Backend is pluggable via a common interface; only the Python-script backend exists in v1. | BuildSpec | Artifact (code, tests, config) |
| **Verifier** | The Airlock gate. Runs the artifact in an **isolated sandbox** against the IR's sample fixtures, checks the output is correct, reports pass/fail with evidence. Can bounce back to Generator (bad code) or Solutioner (bad spec). | Artifact + BuildSpec | Verdicts, redo-requests |
| **Integrator** | Packages the *verified* artifact for handoff: setup/deploy instructions, **credential placeholders (never real creds)**, exactly where it plugs into the existing flow, rollback notes, and the honesty seams (Section 4). | Verified artifact + Workflow Model | Handoff package |

**Pipeline (with its loop):**

```
SP1 intervention → [Solutioner] BuildSpec(IR)
   → [Generator] artifact → [Verifier] sandbox-run against sample fixtures
        ├─ pass → [Integrator] handoff package
        └─ fail → back to Generator (or Solutioner if the spec was wrong)
```

**Why the IR is the point:** the BuildSpec is the tool-agnostic intermediate representation
that makes this a real compiler — produced once by the Solutioner, consumed by *any*
backend (Python now; n8n/agent later). Validating the IR against one real backend is the
whole reason v1 ships a single generator.

---

## 4. Targeting the client's tools — offline, without touching them

The Generator must produce integration code for the client's actual tools while running
offline and never connecting to any of them. It builds against a *description* of each
tool held locally, and where no description exists, emits a clearly-marked seam for a human
to complete. **Approach: hybrid Tool Catalog + adapter stubs.**

- **The Tool Catalog** is a local, offline dataset of integration profiles for common
  business tools — each profile describing that tool's operations, data shapes, and auth
  model *as data*, not a live connection. Ships as versioned reference data in
  `praxis/catalog/` (shared, reviewable, extensible — new profiles are just added data).
- **Known tool** (in catalog) → Generator produces real integration code against the
  profile.
- **Unknown / bespoke tool** (not in catalog) → Generator emits a **well-marked adapter
  interface**: a stub with an explicit contract (e.g. "*implement `fetch_orders()` to
  return records shaped like `{...}` from your internal sheet*"). The human fills it in at
  the airlock. This is how we adapt to a boat with tools we've never seen — a clean, small
  seam instead of forcing them onto a tool we prefer.
- **Verification around the seam:** the Solutioner generates **sample fixtures** for each
  tool's inputs/outputs (grounded in what Discovery learned in SP1). The Verifier runs the
  whole artifact in the sandbox with *fake adapters fed by those fixtures* — so the logic is
  proven end-to-end even though no real tool was ever contacted.

**Two honesty seams, surfaced by the Integrator at handoff (never hidden):**
1. Catalog profiles are descriptions and can drift from a client's live API version →
   handoff says "confirm these endpoints against your current API."
2. Adapter stubs are deliberately unfinished → handoff lists exactly which need a human.

**Engagement vs. catalog:** the catalog is shared package data; only the *engagement-
specific mapping* (this client's tool → which profile; which adapter stubs are needed)
lives on the engagement.

---

## 5. Persistence, sandbox safety, testing

**Persistence — extends `praxis.db` (same engagement, new tables):**

| Table | Holds |
|---|---|
| `build_specs` | the IR per intervention (Solutioner output) |
| `artifacts` | generated code / config / tests (or paths to them) |
| `verifications` | sandbox run results — pass/fail + evidence (Verifier output) |
| `handoff_packages` | the Integrator's deployable package + honesty-seam notes |

**Code location — extends the `praxis/` package:** `solutioner.py`, `generator/` (a backend
interface + `python_script.py`, so n8n/agent backends drop in later), `verifier.py`,
`integrator.py`, `catalog/`, and the `BuildSpec` model.

**Sandbox safety (we execute generated code — this is a real hazard, not hypothetical):**
the Verifier runs each artifact in an **isolated temp working dir, in a subprocess, with no
network, under a timeout**, fed only by sample fixtures — never real credentials or live
systems. The Airlock is enforced mechanically, not by convention. This is acceptable
because Praxis is a local tool the operator runs on their own machine, but it is called out
explicitly rather than assumed.

**Testing (same pytest harness: `.venv\Scripts\python.exe -m pytest tests/ -v`):**
- **Unit:** Solutioner (design → valid IR), Generator (known tool → real integration;
  unknown tool → *marked* adapter stub), Integrator (package + honesty seams present).
- **Integration — the three that matter:**
  - **(a)** full pipeline on a *known-tool* intervention → sandbox-passing artifact,
  - **(b)** the Verifier redo-loop bounces a deliberately-broken generation and converges
    after regeneration,
  - **(c)** an *unknown-tool* intervention → marked adapter stub that still verifies
    end-to-end via a fake adapter fed by fixtures.

---

## 6. Open questions (deferred, not blocking)

- **Second/third backends** (n8n visual flows, agent/prompt packages) — added once the IR
  is validated by the Python-script backend in real use.
- **Catalog seed coverage** — which common tools ship in the v1 catalog. A curation task
  for the implementation plan, not an architecture question.
- **Runtime model calls in generated artifacts** — an artifact may itself call an LLM at
  runtime. Whether generated automation should prefer local/offline models (as Praxis does)
  or is free to call cloud models in the client's environment is a tunable Architect/
  Solutioner preference, deferred to implementation.
- **Everything gated on SP1 existing first** — SP2 cannot begin implementation until SP1's
  `EngagementState` and intervention output are built and stable.
