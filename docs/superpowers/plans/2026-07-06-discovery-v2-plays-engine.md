# Discovery v2 — Plays-Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Phase 0 NO-GO by replacing Discovery v1's single hard-coded focus hint with a content-free **plays** engine plus a deterministic signals layer (canonicalization, grain guard, vagueness/novelty), and a rewritten extraction prompt — so Discovery builds consolidated, facet-complete workflow graphs.

**Architecture:** A small deterministic `discovery_signals` module powers node canonicalization (surface dedup), a step-label grain guard, and answer-signals. A `plays` registry of content-free interview tactics decides each question via `select_play(state)`. `discovery.py` is rewired to use both; the rest of the pipeline (models, coverage, harness, scoring, gate) is untouched.

**Tech Stack:** Python 3, `asyncio`, local Ollama, `pytest` + `pytest-asyncio`, stdlib `re`/`dataclasses`. No new deps.

## Global Constraints

- **Ocean Principle — content, not content.** Every play, signal, and heuristic is about *interview dynamics*, never business domain. No play/signal may classify content ("this is a tool", "this is invoicing") or hardcode a business noun. Node typing stays the LLM's job. (Spec §1, §6.)
- **Deterministic layer is pure:** `discovery_signals` and `plays` make NO LLM/network calls. Only `discovery.next_question`/`extract_deltas` call the model.
- **Reuse, don't rebuild:** do NOT modify `praxis/models.py`, `praxis/coverage.py`, `praxis/llm_client.py`, `praxis/eval/*`. v2 touches only `discovery_signals.py` (new), `plays.py` (new), `discovery.py`, `discovery_prompts.py`.
- **Test command:** `.venv\Scripts\python.exe -m pytest tests/praxis/ -v`
- **TDD, commit per task.** The existing 34 tests must stay green (Task 5).
- **Deferred (OUT of scope):** the learning loop (machine-proposed plays), semantic dedup, downstream agents.

---

## File Structure

- `praxis/discovery_signals.py` — NEW. `canonical_label`, `is_valid_step_label`, `is_vague`, `introduces_novelty`. Pure.
- `praxis/plays.py` — NEW. `InterviewState`, `Play`, the seed `REGISTRY`, `select_play`.
- `praxis/discovery.py` — MODIFY. Canonical dedup in `_get_or_add`; grain guard in `extract_deltas`; `next_question` routes through `select_play`; remove `focus_hint_for`.
- `praxis/discovery_prompts.py` — MODIFY. Rewrite `EXTRACTION_SYSTEM` (short verb-object steps + same-turn facet edges).
- Tests mirror each.

---

## Task 1: Deterministic signals

**Files:**
- Create: `praxis/discovery_signals.py`
- Test: `tests/praxis/test_signals.py`

**Interfaces:**
- Produces:
  - `canonical_label(raw: str) -> str` — lowercase, strip punctuation, strip leading articles, collapse whitespace.
  - `is_valid_step_label(raw: str) -> bool` — False if empty, >5 words, contains a hedge word, or contains `?`.
  - `is_vague(answer: str) -> bool` — True if empty, <5 words, or contains a hedge word.

(Spec §4 also names an `introduces_novelty` signal; it is **deferred** — no seed play consumes it yet, so building it now would be dead code. Add it with the play that needs it.)

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_signals.py
from praxis.discovery_signals import (
    canonical_label, is_valid_step_label, is_vague,
)

def test_canonical_label_collapses_articles_case_punct():
    assert canonical_label("The Notebook!") == "notebook"
    assert canonical_label("my notebook") == "notebook"
    assert canonical_label("notebook") == "notebook"
    assert canonical_label("the order sheet") == "order sheet"

def test_is_valid_step_label():
    assert is_valid_step_label("take order") is True
    assert is_valid_step_label("match invoices to pos") is True         # 4 words
    assert is_valid_step_label("hoping someone ordered scones") is False # hedge
    assert is_valid_step_label("we just grab whatever looks edible now") is False  # >5 words
    assert is_valid_step_label("what do you file it in?") is False       # question
    assert is_valid_step_label("") is False

def test_is_vague():
    assert is_vague("uh, we do stuff") is True                 # <5 words
    assert is_vague("maybe we sort of handle it later somehow") is True  # hedge
    assert is_vague("I take the order in my notebook then bake") is False

```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_signals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.discovery_signals'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/discovery_signals.py
"""Deterministic, content-free signals for Discovery v2. No LLM, no network.
Reads conversational FORM (length, hedges, novelty) and normalizes labels —
never classifies business content (Ocean Principle)."""
import re

_ARTICLES = {"the", "a", "an", "my", "our", "your", "their", "his", "her", "its"}
_HEDGE = {"hoping", "hope", "maybe", "because", "wish", "guess", "guessing",
          "probably", "kinda", "sorta", "somehow", "whatever"}


def canonical_label(raw: str) -> str:
    s = (raw or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    toks = [t for t in s.split() if t]
    while toks and toks[0] in _ARTICLES:
        toks.pop(0)
    return " ".join(toks)


def is_valid_step_label(raw: str) -> bool:
    s = (raw or "").strip()
    if not s:
        return False
    if "?" in s:
        return False
    words = s.split()
    if len(words) > 5:
        return False
    low = {w.lower().strip(".,!?") for w in words}
    if low & _HEDGE:
        return False
    return True


def is_vague(answer: str) -> bool:
    a = (answer or "").strip()
    if not a:
        return True
    words = a.split()
    if len(words) < 5:
        return True
    low = {w.lower().strip(".,!?") for w in words}
    return bool(low & _HEDGE)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_signals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/discovery_signals.py tests/praxis/test_signals.py
git commit -m "feat(praxis): deterministic content-free discovery signals"
```

---

## Task 2: The plays engine

**Files:**
- Create: `praxis/plays.py`
- Test: `tests/praxis/test_plays.py`

**Interfaces:**
- Consumes: `praxis.coverage.analyze_coverage`/`biggest_gap`; `praxis.discovery_signals.is_vague`; `praxis.models` types.
- Produces:
  - `@dataclass InterviewState(model, last_answer: str = "")` with a `coverage` property returning `analyze_coverage(self.model)`.
  - `@dataclass Play(id: str, kind: str, priority: int, matches: Callable, focus: Callable)`.
  - `REGISTRY: list[Play]` — the seed plays.
  - `select_play(state: InterviewState) -> Play` — highest-priority play whose `matches(state)` is True (registry always includes an always-matching fallback, so never None).

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_plays.py
from praxis.plays import InterviewState, select_play, REGISTRY
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence

def _ev(): return [Evidence("q", 1)]

def _step_missing_facets(m, label):
    return m.add_node(NodeType.STEP, label, _ev())

def test_no_steps_selects_establish_first_step():
    st = InterviewState(WorkflowModel(), last_answer="hi")
    assert select_play(st).id == "establish_first_step"

def test_step_missing_facets_selects_complete_step_facets():
    m = WorkflowModel(); _step_missing_facets(m, "take order")
    st = InterviewState(m, last_answer="we take orders")
    play = select_play(st)
    assert play.id == "complete_step_facets"
    assert "take order" in play.focus(st)

def test_vague_answer_selects_probe_when_no_facet_gap():
    # a fully-covered step so complete_step_facets does not fire; vague answer -> probe
    m = WorkflowModel()
    s = m.add_node(NodeType.STEP, "take order", _ev())
    a = m.add_node(NodeType.ACTOR, "me", _ev())
    t = m.add_node(NodeType.TOOL, "sheet", _ev())
    o = m.add_node(NodeType.ARTIFACT, "slip", _ev())
    m.add_edge(EdgeType.PERFORMS, a.id, s.id, _ev())
    m.add_edge(EdgeType.USES, s.id, t.id, _ev())
    m.add_edge(EdgeType.PRODUCES, s.id, o.id, _ev())
    st = InterviewState(m, last_answer="uh dunno")
    assert select_play(st).id == "probe_after_vague"

def test_registry_has_always_matching_fallback():
    # a weird state still yields a play (never None)
    st = InterviewState(WorkflowModel(), last_answer="a fairly long clear answer here")
    assert select_play(st) is not None

def test_no_play_leaks_business_content():
    DENY = {"invoice", "bakery", "notebook", "quickbooks", "spreadsheet",
            "crm", "email", "order", "customer"}
    m = WorkflowModel(); m.add_node(NodeType.STEP, "stepx", _ev())
    st = InterviewState(m, last_answer="uh")
    for p in REGISTRY:
        if p.matches(st):
            words = set(p.focus(st).lower().replace("'", " ").split())
            assert not (words & DENY), f"play {p.id} leaked a business noun"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_plays.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.plays'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/plays.py
"""Content-free interview 'plays'. Each play is a rule about interview DYNAMICS
(trigger -> question directive), never about business domain (Ocean Principle).
This registry is the substrate a future learning loop will extend."""
from dataclasses import dataclass, field
from typing import Callable
from praxis.models import NodeType, EdgeType
from praxis.coverage import analyze_coverage, biggest_gap
from praxis.discovery_signals import is_vague

_FACET_Q = {
    "actor": "who does it",
    "tool": "what tool they use",
    "input": "what they start with",
    "output": "what it produces",
}


@dataclass
class InterviewState:
    model: object
    last_answer: str = ""

    @property
    def coverage(self):
        return analyze_coverage(self.model)


@dataclass
class Play:
    id: str
    kind: str
    priority: int
    matches: Callable
    focus: Callable


def _steps(state):
    return state.model.nodes_of(NodeType.STEP)


def _nonfriction_gap(state):
    gap = biggest_gap(state.coverage)
    if not gap:
        return None
    facets = [f for f in gap.missing if f in _FACET_Q]
    return (gap, facets) if facets else None


def _satisfied_step_without_friction(state):
    m = state.model
    for s in _steps(state):
        out_edges = m.edges_from(s.id)
        in_edges = [e for e in m.edges.values() if e.target == s.id]
        has_actor = any(e.type == EdgeType.PERFORMS for e in in_edges)
        has_tool = any(e.type == EdgeType.USES for e in out_edges)
        has_io = any(e.type in (EdgeType.CONSUMES, EdgeType.PRODUCES) for e in out_edges)
        has_friction = any(e.type == EdgeType.CAUSES for e in out_edges)
        if has_actor and has_tool and has_io and not has_friction:
            return s
    return None


def _sequence_count(state):
    return sum(1 for e in state.model.edges.values() if e.type == EdgeType.SEQUENCE)


REGISTRY = [
    Play("establish_first_step", "question", 90,
         matches=lambda st: len(_steps(st)) == 0,
         focus=lambda st: ("No step is mapped yet. Ask them to name, in a few words, "
                           "the very first thing that happens when the work starts.")),
    Play("complete_step_facets", "question", 70,
         matches=lambda st: _nonfriction_gap(st) is not None,
         focus=lambda st: (lambda g: f"For the step '{g[0].step_label}', find out: "
                           + ", ".join(_FACET_Q[f] for f in g[1])
                           + ". Ask one concrete question about it.")(_nonfriction_gap(st))),
    Play("probe_after_vague", "question", 60,
         matches=lambda st: is_vague(st.last_answer) and len(_steps(st)) > 0,
         focus=lambda st: ("Their last answer was vague. Ask them to walk you through the "
                           "most recent actual time this happened, concretely, start to finish.")),
    Play("trace_sequence", "question", 40,
         matches=lambda st: len(_steps(st)) >= 1 and _sequence_count(st) < len(_steps(st)) - 1,
         focus=lambda st: ("Ask what happens immediately after the most recently "
                           "described step.")),
    Play("surface_friction", "question", 20,
         matches=lambda st: _satisfied_step_without_friction(st) is not None,
         focus=lambda st: (f"For the step '{_satisfied_step_without_friction(st).label}', "
                           "ask what usually goes wrong or slows them down there.")),
    Play("fallback", "question", 0,
         matches=lambda st: True,
         focus=lambda st: ("Ask what happens next in the process, or which part of this "
                           "work is the most annoying or error-prone.")),
]


def select_play(state: InterviewState) -> Play:
    candidates = [p for p in REGISTRY if p.matches(state)]
    return max(candidates, key=lambda p: p.priority)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_plays.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/plays.py tests/praxis/test_plays.py
git commit -m "feat(praxis): content-free interview plays engine"
```

---

## Task 3: Canonical dedup + grain guard in discovery

**Files:**
- Modify: `praxis/discovery.py` (`_get_or_add` at lines 35-41; `extract_deltas` add_node branch at lines 24-25)
- Test: `tests/praxis/test_discovery_v2_extract.py`

**Interfaces:**
- Consumes: `praxis.discovery_signals.canonical_label`, `is_valid_step_label`.
- Changes behavior of existing `extract_deltas` (drops invalid step labels) and `_get_or_add` (canonical dedup). Signatures unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_discovery_v2_extract.py
import pytest
from praxis.models import WorkflowModel, NodeType
from praxis.discovery import extract_deltas, apply_deltas

class FakeClient:
    def __init__(self, payload): self.payload = payload
    async def complete_json(self, system, user, **kw): return self.payload

@pytest.mark.asyncio
async def test_grain_guard_drops_fragment_steps():
    payload = {"deltas": [
        {"op": "add_node", "node_type": "step", "label": "take order", "quote": "I take the order"},
        {"op": "add_node", "node_type": "step",
         "label": "hoping someone actually ordered scones", "quote": "hoping someone ordered"},
    ]}
    deltas = await extract_deltas(FakeClient(payload), [], "msg", turn=1)
    labels = [d["label"] for d in deltas if d["op"] == "add_node"]
    assert "take order" in labels
    assert "hoping someone actually ordered scones" not in labels

@pytest.mark.asyncio
async def test_canonical_dedup_merges_surface_variants():
    m = WorkflowModel()
    deltas = [
        {"op": "add_node", "node_type": "tool", "label": "the notebook", "quote": "the notebook"},
        {"op": "add_node", "node_type": "tool", "label": "my notebook", "quote": "my notebook"},
        {"op": "add_node", "node_type": "tool", "label": "notebook", "quote": "a notebook"},
    ]
    apply_deltas(m, deltas, turn=1)
    assert len(m.nodes_of(NodeType.TOOL)) == 1   # all collapse to one canonical node
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_v2_extract.py -v`
Expected: FAIL — `test_canonical_dedup_merges_surface_variants` fails (3 nodes, not 1), and the grain test fails (fragment kept).

- [ ] **Step 3: Write minimal implementation**

In `praxis/discovery.py`, update the import line (line 3-5 region) to add the signals import:

```python
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P
from praxis.discovery_signals import canonical_label, is_valid_step_label
```

(Remove the `from praxis.coverage import analyze_coverage, biggest_gap` line — it is no longer used here after Task 4; if Task 3 runs before Task 4, leave it and it will be removed in Task 4. Keeping it is harmless for Task 3.)

Replace the `extract_deltas` add_node acceptance branch (the `if op == "add_node" ...: out.append(d)` block) with a grain guard:

```python
            if op == "add_node" and d.get("node_type") in _VALID_NODE and d.get("label"):
                if d["node_type"] == "step" and not is_valid_step_label(d["label"]):
                    continue
                out.append(d)
```

Replace `_get_or_add` with canonical matching:

```python
def _get_or_add(model, label, ntype, ev):
    target = canonical_label(label)
    for n in model.nodes.values():
        if n.type == ntype and canonical_label(n.label) == target:
            n.evidence.append(ev)
            n.confidence.evidence_count += 1
            return n
    return model.add_node(ntype, label, [ev])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_v2_extract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/discovery.py tests/praxis/test_discovery_v2_extract.py
git commit -m "feat(praxis): canonical node dedup + step grain guard"
```

---

## Task 4: Route questioning through plays + rewrite extraction prompt

**Files:**
- Modify: `praxis/discovery.py` (`focus_hint_for` lines 70-83 removed; `next_question` lines 86-92 rewired; drop the unused coverage import)
- Modify: `praxis/discovery_prompts.py` (`EXTRACTION_SYSTEM` lines 6-16)
- Modify: `tests/praxis/test_discovery_question.py` (drop the two `focus_hint_for` tests + its import)

**Interfaces:**
- Consumes: `praxis.plays.InterviewState`, `select_play`.
- `next_question(client, model, history)` signature unchanged; now selects a play from the last client answer + graph and uses its `focus` as the interviewer directive. `focus_hint_for` is removed.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/praxis/test_discovery_question.py (new test)
import pytest
from praxis.discovery import next_question
from praxis.models import WorkflowModel, NodeType, Evidence

class FocusCapturingClient:
    def __init__(self): self.last_user = None
    async def complete(self, system, messages, **kw):
        self.last_user = messages[-1]["content"]
        return "So what tool do you use to take the order?"

@pytest.mark.asyncio
async def test_next_question_routes_through_a_play():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "take order", [Evidence("we take orders", 1)])
    fc = FocusCapturingClient()
    q = await next_question(fc, m, [{"role": "user", "content": "we take orders"}])
    # complete_step_facets fires: the directive names the step + a facet
    assert "take order" in fc.last_user
    assert q.endswith("?")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_question.py::test_next_question_routes_through_a_play -v`
Expected: FAIL at import/attribute time or assertion (plays not yet wired).

- [ ] **Step 3: Write minimal implementation**

In `praxis/discovery.py`: ensure the coverage import is removed and plays imported. The top imports become:

```python
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P
from praxis.discovery_signals import canonical_label, is_valid_step_label
from praxis.plays import InterviewState, select_play
```

Delete the `_FACET_Q` dict and the entire `focus_hint_for` function (lines 70-83). Replace `next_question` with:

```python
async def next_question(client, model, history):
    last = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last = m.get("content", "")
            break
    state = InterviewState(model, last_answer=last)
    hint = select_play(state).focus(state)
    user = P.build_interviewer_user(history, hint)
    text = await client.complete(P.INTERVIEWER_SYSTEM,
                                 [{"role": "user", "content": user}],
                                 max_tokens=120, temperature=0.7)
    return text.strip()
```

In `tests/praxis/test_discovery_question.py`: change the import line `from praxis.discovery import next_question, focus_hint_for` to `from praxis.discovery import next_question`, and DELETE the two tests `test_focus_hint_targets_the_biggest_gap` and `test_focus_hint_when_no_gaps_asks_sequence_or_pain` (they test the removed function). Keep `test_next_question_passes_focus_to_model` (it still passes: a step "file it" missing facets makes `complete_step_facets` fire, whose focus contains "file it").

In `praxis/discovery_prompts.py`, replace `EXTRACTION_SYSTEM` (lines 6-16) with:

```python
EXTRACTION_SYSTEM = """You map a business's workflow into a graph using ONLY the person's \
own words as evidence. Never invent steps, tools, or people they did not mention.

Return JSON {"deltas":[...]}. Each delta is one of:
- {"op":"add_node","node_type":"step|actor|tool|artifact|friction","label":"<short, their words>","quote":"<exact phrase>"}
- {"op":"add_edge","edge_type":"sequence|performs|uses|produces|consumes|causes","source_label":"..","source_type":"..","target_label":"..","target_type":"..","quote":"<exact phrase>"}

STEPS — the most important rule:
- A step is ONE concrete action, labelled as a SHORT verb-object phrase in their words: "take order", "bake bread", "send invoice". Max 4 words.
- Do NOT make steps out of feelings, hopes, guesses, or complaints ("hoping it sold", "before it burns", "we just wing it"). Those are frictions at most, or nothing.
- When you add a step, in the SAME response also emit the edges the person stated for it:
    actor performs step (performs: actor -> step),
    step uses tool (uses: step -> tool),
    step consumes its input (consumes: step -> artifact),
    step produces its output (produces: step -> artifact).

GENERAL:
- Every delta MUST include a verbatim quote from the latest message. No quote -> omit it.
- Labels are short and in the speaker's vocabulary ("the order sheet", not "Order Management System").
- Only extract what THIS message adds; do not restate the whole graph."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_question.py -v`
Expected: PASS (the two removed tests are gone; the new routing test and the retained focus test pass)

- [ ] **Step 5: Commit**

```bash
git add praxis/discovery.py praxis/discovery_prompts.py tests/praxis/test_discovery_question.py
git commit -m "feat(praxis): route questioning through plays; rewrite extraction prompt"
```

---

## Task 5: Full regression + re-run the gate

No new unit code — this task confirms no regression and runs the actual v2 experiment against the same gate.

- [ ] **Step 1: Run the full praxis suite**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/ -v`
Expected: ALL pass. If any existing test broke because of the changed extraction/dedup contract, fix the TEST to reflect the intended new behavior (do not weaken v2 to satisfy a v1 assumption); if a change surfaces a real bug, report it. Note that valid short labels used in existing tests (`take order`, `send quote`, `do the thing`, `match invoices to POs`, `me`, `sheet`) all pass the grain guard and canonical dedup, so breakage is not expected.

- [ ] **Step 2: Commit any test updates**

```bash
git add -A && git commit -m "test(praxis): align tests with v2 extraction/dedup contract" || echo "no changes"
```

- [ ] **Step 3: Confirm Ollama, then re-run the gate**

Run: `ollama list` (expect `qwen3.5:9b`).
Run: `.venv\Scripts\python.exe -m praxis.eval.run_phase0`
Expected: `phase0_out/` refreshed with per-scenario JSON, `scorecards.json`, `gate_report.json`; the report prints.

- [ ] **Step 4: Compare against the v1 verdict and record**

The bar and scenarios are unchanged (anti-confirmation). Write `phase0_out/VERDICT_v2.md`: per-scenario coverage/connected/grain/orphans, the auto_pass_rate, and the go/no-go call. **Success = coverage decisively off 0.00 and a majority auto-pass.** If it still fails, the diagnosis dictates the next branch (semantic dedup, or a stronger extraction model) — not more hand-plays. Commit:

```bash
git add phase0_out/VERDICT_v2.md phase0_out/gate_report.json phase0_out/scorecards.json
git commit -m "chore(praxis): record Discovery v2 gate verdict"
```

---

## Out of scope (unchanged from spec §9)

The learning loop (machine-proposed plays), semantic dedup, and all downstream agents remain deferred until v2 clears the gate.
