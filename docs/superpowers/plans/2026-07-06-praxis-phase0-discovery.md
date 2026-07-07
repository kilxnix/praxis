# Praxis Phase 0 — Discovery Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Discovery agent and an evaluation harness that proves — or disproves — whether an offline LLM can conduct a client-facing business-workflow interview and produce a solid, grounded, appropriately-grained workflow graph. This is the existential go/no-go gate; nothing downstream is built until it passes.

**Architecture:** A fresh `praxis/` package. Discovery grows an emergent evidence-graph (`WorkflowModel`) over a conversation: each client turn is *extracted* into graph deltas (nodes/edges, each carrying an evidence quote), a pure `coverage` function reports gaps, and the *interviewer* asks the next question aimed at the biggest gap. An eval harness runs Discovery against LLM-simulated difficult non-expert clients, persists transcript + graph + compute cost, and scores each run against the Phase 0 criteria (connected / grained / grounded / honest-about-gaps).

**Tech Stack:** Python 3, `asyncio`, `httpx`, local Ollama (`qwen3.5:9b` default), `pytest` + `pytest-asyncio`, stdlib `dataclasses`/`json`. No new third-party deps.

## Global Constraints

- **Strictly offline.** All model calls go to local Ollama via `praxis/llm_client.py`. No cloud calls, no network except `localhost:11434`. (Spec §2 decision 5.)
- **Ocean Principle — content, not process.** Extraction and questioning must use the *universal structural primitives* (Step / Actor / Tool / Artifact / Friction) and the client's own words. No industry templates or predefined domain categories. (Spec §2, §4.)
- **Evidence-required, mechanically.** A node or edge with no evidence quote must not be persisted. No exceptions. (Spec §4.)
- **Fresh prompts, no wellness carryover.** All prompt/persona text is written from scratch for a brisk business interview — do NOT copy `interviewer/prompt_builder.py` or `persona_builder.py` text. (Spec §7.)
- **Test command:** `.venv\Scripts\python.exe -m pytest tests/praxis/ -v`
- **Commit after every task.** TDD: failing test first, minimal code, green, commit.
- **Deferred until the gate passes (explicitly OUT of scope here):** SQLite persistence (`praxis.db`), the Analyst/Architect/Business-case/Skeptic/Principal agents, the deliverable renderer, the FastAPI/web UI, SP2 entirely. Phase 0 uses JSON-file persistence only.

---

## File Structure

- `praxis/__init__.py` — package marker.
- `praxis/models.py` — `WorkflowModel` and its parts (nodes, edges, evidence, confidence) + JSON (de)serialization.
- `praxis/llm_client.py` — offline Ollama client (`complete`, `complete_json`), adapted from `interviewer/llm_client.py` with wellness methods stripped.
- `praxis/coverage.py` — pure functions: given a `WorkflowModel`, compute a `CoverageReport` (gaps, orphans, evidence-less nodes, thin areas).
- `praxis/discovery_prompts.py` — from-scratch system/persona + extraction/interviewer prompt builders.
- `praxis/discovery.py` — `extract_deltas()` and `next_question()` (the two LLM-touching Discovery operations) + `apply_deltas()`.
- `praxis/session.py` — `DiscoverySession` turn loop; runs live or against a scripted/simulated client; `is_intake_complete()`.
- `praxis/eval/__init__.py`
- `praxis/eval/scenarios.py` — difficult non-expert client personas (data).
- `praxis/eval/client_sim.py` — LLM role-play of a scenario client.
- `praxis/eval/harness.py` — run Discovery vs a simulated client; persist artifacts + metrics.
- `praxis/eval/scoring.py` — automated structural checks + human-rubric scorecard template + Phase 0 aggregate report.
- `praxis/cli.py` — live terminal Discovery interview against Ollama.
- `tests/praxis/` — mirrors the above.

---

## Task 1: WorkflowModel core

**Files:**
- Create: `praxis/__init__.py` (empty)
- Create: `praxis/models.py`
- Test: `tests/praxis/__init__.py` (empty), `tests/praxis/test_models.py`

**Interfaces:**
- Produces:
  - `NodeType(str, Enum)`: `STEP, ACTOR, TOOL, ARTIFACT, FRICTION`
  - `EdgeType(str, Enum)`: `SEQUENCE, PERFORMS, USES, PRODUCES, CONSUMES, CAUSES`
  - `Evidence(quote: str, turn: int)` dataclass
  - `ElementConfidence(value: float = 0.0, evidence_count: int = 0)` dataclass
  - `WorkflowNode(id: str, type: NodeType, label: str, evidence: list[Evidence], confidence: ElementConfidence)`
  - `WorkflowEdge(id: str, type: EdgeType, source: str, target: str, evidence: list[Evidence], confidence: ElementConfidence)`
  - `WorkflowModel` with: `nodes: dict[str, WorkflowNode]`, `edges: dict[str, WorkflowEdge]`, methods `add_node(type,label,evidence,node_id=None)->WorkflowNode`, `add_edge(type,source,target,evidence,edge_id=None)->WorkflowEdge`, `find_node(label,type)->WorkflowNode|None`, `nodes_of(type)->list`, `edges_from(node_id)->list`, `to_dict()->dict`, `from_dict(d)->WorkflowModel` (classmethod).

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_models.py
from praxis.models import (
    WorkflowModel, NodeType, EdgeType, Evidence,
)

def test_add_node_and_edge_roundtrip():
    m = WorkflowModel()
    step = m.add_node(NodeType.STEP, "match invoices to POs",
                      [Evidence("we match every invoice to a PO by hand", turn=2)])
    actor = m.add_node(NodeType.ACTOR, "bookkeeper",
                       [Evidence("our bookkeeper does it", turn=2)])
    edge = m.add_edge(EdgeType.PERFORMS, actor.id, step.id,
                      [Evidence("our bookkeeper does it", turn=2)])

    assert m.find_node("match invoices to POs", NodeType.STEP) is step
    assert m.nodes_of(NodeType.ACTOR) == [actor]
    assert m.edges_from(actor.id) == [edge]

    restored = WorkflowModel.from_dict(m.to_dict())
    assert restored.to_dict() == m.to_dict()
    assert restored.nodes[step.id].evidence[0].quote.startswith("we match")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/models.py
"""Praxis Workflow Model — an emergent, evidence-grounded graph of how a business works.

Nodes and edges are named in the client's own words; every one carries the literal
quote that justifies it (Ocean Principle §4, evidence-required Global Constraint).
"""
from dataclasses import dataclass, field, asdict
from enum import Enum


class NodeType(str, Enum):
    STEP = "step"
    ACTOR = "actor"
    TOOL = "tool"
    ARTIFACT = "artifact"
    FRICTION = "friction"


class EdgeType(str, Enum):
    SEQUENCE = "sequence"    # step -> next step
    PERFORMS = "performs"    # actor -> step
    USES = "uses"            # step -> tool
    PRODUCES = "produces"    # step -> artifact
    CONSUMES = "consumes"    # step -> artifact
    CAUSES = "causes"        # step -> friction


@dataclass
class Evidence:
    quote: str
    turn: int


@dataclass
class ElementConfidence:
    value: float = 0.0
    evidence_count: int = 0


@dataclass
class WorkflowNode:
    id: str
    type: NodeType
    label: str
    evidence: list = field(default_factory=list)
    confidence: ElementConfidence = field(default_factory=ElementConfidence)


@dataclass
class WorkflowEdge:
    id: str
    type: EdgeType
    source: str
    target: str
    evidence: list = field(default_factory=list)
    confidence: ElementConfidence = field(default_factory=ElementConfidence)


class WorkflowModel:
    def __init__(self):
        self.nodes: dict = {}
        self.edges: dict = {}
        self._n = 0

    def _next_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def add_node(self, type: NodeType, label: str, evidence: list, node_id: str = None) -> WorkflowNode:
        node_id = node_id or self._next_id("n")
        node = WorkflowNode(
            id=node_id, type=NodeType(type), label=label,
            evidence=list(evidence),
            confidence=ElementConfidence(value=0.5, evidence_count=len(evidence)),
        )
        self.nodes[node_id] = node
        return node

    def add_edge(self, type: EdgeType, source: str, target: str, evidence: list, edge_id: str = None) -> WorkflowEdge:
        edge_id = edge_id or self._next_id("e")
        edge = WorkflowEdge(
            id=edge_id, type=EdgeType(type), source=source, target=target,
            evidence=list(evidence),
            confidence=ElementConfidence(value=0.5, evidence_count=len(evidence)),
        )
        self.edges[edge_id] = edge
        return edge

    def find_node(self, label: str, type: NodeType):
        for n in self.nodes.values():
            if n.type == NodeType(type) and n.label.strip().lower() == label.strip().lower():
                return n
        return None

    def nodes_of(self, type: NodeType) -> list:
        return [n for n in self.nodes.values() if n.type == NodeType(type)]

    def edges_from(self, node_id: str) -> list:
        return [e for e in self.edges.values() if e.source == node_id]

    def to_dict(self) -> dict:
        return {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkflowModel":
        m = cls()
        for nd in d.get("nodes", []):
            ev = [Evidence(**e) for e in nd["evidence"]]
            m.nodes[nd["id"]] = WorkflowNode(
                id=nd["id"], type=NodeType(nd["type"]), label=nd["label"],
                evidence=ev, confidence=ElementConfidence(**nd["confidence"]),
            )
        for ed in d.get("edges", []):
            ev = [Evidence(**e) for e in ed["evidence"]]
            m.edges[ed["id"]] = WorkflowEdge(
                id=ed["id"], type=EdgeType(ed["type"]), source=ed["source"],
                target=ed["target"], evidence=ev,
                confidence=ElementConfidence(**ed["confidence"]),
            )
        ids = [int(x[1:]) for x in list(m.nodes) + list(m.edges) if x[1:].isdigit()]
        m._n = max(ids) if ids else 0
        return m
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/__init__.py praxis/models.py tests/praxis/__init__.py tests/praxis/test_models.py
git commit -m "feat(praxis): WorkflowModel evidence-graph core"
```

---

## Task 2: Offline LLM client

**Files:**
- Create: `praxis/llm_client.py`
- Test: `tests/praxis/test_llm_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `OllamaClient(base_url="http://localhost:11434", model="qwen3.5:9b")`
  - `async complete(system: str, messages: list[dict], max_tokens=512, temperature=0.7) -> str`
  - `async complete_json(system: str, user: str, max_tokens=768, temperature=0.2) -> dict`
  - `parse_json(text: str) -> dict` (static; the fallback chain)
  - `async close()`

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_llm_client.py
from praxis.llm_client import OllamaClient

def test_parse_json_strips_code_fences_and_prose():
    raw = 'Sure!\n```json\n{"nodes": [{"label": "invoicing"}]}\n```\nHope that helps.'
    assert OllamaClient.parse_json(raw) == {"nodes": [{"label": "invoicing"}]}

def test_parse_json_returns_empty_dict_on_garbage():
    assert OllamaClient.parse_json("no json here at all") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.llm_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/llm_client.py
"""Offline Ollama client for Praxis. Adapted from interviewer/llm_client.py,
wellness-specific methods removed. All calls hit local Ollama only."""
import json
import os
import httpx

DEFAULT_MODEL = os.environ.get("PRAXIS_MODEL", "qwen3.5:9b")


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = DEFAULT_MODEL):
        self.model = model
        self._http = httpx.AsyncClient(base_url=base_url, timeout=180.0)

    async def close(self):
        await self._http.aclose()

    async def complete(self, system, messages, max_tokens=512, temperature=0.7) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        r = await self._http.post("/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"]

    async def complete_json(self, system, user, max_tokens=768, temperature=0.2) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        r = await self._http.post("/api/chat", json=payload)
        r.raise_for_status()
        return self.parse_json(r.json()["message"]["content"])

    @staticmethod
    def parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        cleaned = text.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass
        if "{" in cleaned and "}" in cleaned:
            try:
                return json.loads(cleaned[cleaned.index("{"): cleaned.rindex("}") + 1])
            except (json.JSONDecodeError, TypeError):
                pass
        return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_llm_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/llm_client.py tests/praxis/test_llm_client.py
git commit -m "feat(praxis): offline Ollama client with JSON fallback parsing"
```

---

## Task 3: Coverage analysis (the backbone of probing + structural checks)

**Files:**
- Create: `praxis/coverage.py`
- Test: `tests/praxis/test_coverage.py`

**Interfaces:**
- Consumes: `WorkflowModel`, `NodeType`, `EdgeType` from Task 1.
- Produces:
  - `@dataclass StepGap(step_id, step_label, missing: list[str])` where `missing` ⊆ `{"actor","tool","input","output","friction"}`
  - `@dataclass CoverageReport(step_gaps: list[StepGap], orphan_steps: list[str], evidenceless: list[str], grain_outliers: list[str], overall: float)`
  - `analyze_coverage(model: WorkflowModel) -> CoverageReport`
  - `biggest_gap(report: CoverageReport) -> StepGap | None` (the step with the most missing facets; ties → first)

Coverage rules (the who/tool/in/out/breaks sweep, Spec §4):
- For each STEP, it "has an actor" if some `PERFORMS` edge targets it; "has a tool" if a `USES` edge sources from it; "input"/"output" if `CONSUMES`/`PRODUCES` edges source from it; "friction" is optional-but-tracked (its absence is not a gap by itself, but reported).
- `orphan_steps`: STEP nodes with zero connected edges.
- `evidenceless`: any node/edge id whose `evidence` list is empty (Global Constraint guard; should normally be empty because Task 4 drops them, but the check exists as a safety net for scoring).
- `grain_outliers`: STEP labels longer than 8 words OR containing " and " twice+ (heuristic for "the sales department does everything" blobs).
- `overall`: fraction of steps that have actor+tool+at least one of input/output, in `[0,1]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_coverage.py
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis.coverage import analyze_coverage, biggest_gap

def _ev(t=1): return [Evidence("quote", t)]

def test_coverage_flags_missing_facets_and_orphans():
    m = WorkflowModel()
    s1 = m.add_node(NodeType.STEP, "receive invoice", _ev())
    a1 = m.add_node(NodeType.ACTOR, "clerk", _ev())
    t1 = m.add_node(NodeType.TOOL, "email", _ev())
    art = m.add_node(NodeType.ARTIFACT, "invoice pdf", _ev())
    m.add_edge(EdgeType.PERFORMS, a1.id, s1.id, _ev())
    m.add_edge(EdgeType.USES, s1.id, t1.id, _ev())
    m.add_edge(EdgeType.CONSUMES, s1.id, art.id, _ev())
    s2 = m.add_node(NodeType.STEP, "file it", _ev())  # orphan: no edges

    rep = analyze_coverage(m)
    assert s2.id in rep.orphan_steps
    gap = biggest_gap(rep)
    assert gap.step_id == s2.id
    assert set(gap.missing) >= {"actor", "tool"}
    assert 0.0 <= rep.overall <= 1.0

def test_evidenceless_node_is_flagged():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "ghost step", [])
    rep = analyze_coverage(m)
    assert len(rep.evidenceless) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_coverage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.coverage'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/coverage.py
"""Pure coverage analysis over a WorkflowModel. Drives Discovery's next question
and feeds the Phase 0 structural scorecard. No LLM, fully deterministic."""
from dataclasses import dataclass, field
from praxis.models import WorkflowModel, NodeType, EdgeType

FACETS = ("actor", "tool", "input", "output", "friction")


@dataclass
class StepGap:
    step_id: str
    step_label: str
    missing: list = field(default_factory=list)


@dataclass
class CoverageReport:
    step_gaps: list = field(default_factory=list)
    orphan_steps: list = field(default_factory=list)
    evidenceless: list = field(default_factory=list)
    grain_outliers: list = field(default_factory=list)
    overall: float = 0.0


def _grain_outlier(label: str) -> bool:
    return len(label.split()) > 8 or label.lower().count(" and ") >= 2


def analyze_coverage(model: WorkflowModel) -> CoverageReport:
    rep = CoverageReport()

    for elem_id, elem in list(model.nodes.items()) + list(model.edges.items()):
        if not elem.evidence:
            rep.evidenceless.append(elem_id)

    steps = model.nodes_of(NodeType.STEP)
    satisfied = 0
    for s in steps:
        out_edges = model.edges_from(s.id)
        in_edges = [e for e in model.edges.values() if e.target == s.id]
        has = {
            "actor": any(e.type == EdgeType.PERFORMS for e in in_edges),
            "tool": any(e.type == EdgeType.USES for e in out_edges),
            "input": any(e.type == EdgeType.CONSUMES for e in out_edges),
            "output": any(e.type == EdgeType.PRODUCES for e in out_edges),
            "friction": any(e.type == EdgeType.CAUSES for e in out_edges),
        }
        if not out_edges and not in_edges:
            rep.orphan_steps.append(s.id)
        missing = [f for f in FACETS if not has[f]]
        if missing:
            rep.step_gaps.append(StepGap(s.id, s.label, missing))
        if has["actor"] and has["tool"] and (has["input"] or has["output"]):
            satisfied += 1
        if _grain_outlier(s.label):
            rep.grain_outliers.append(s.id)

    rep.overall = (satisfied / len(steps)) if steps else 0.0
    return rep


def biggest_gap(report: CoverageReport):
    ranked = sorted(
        report.step_gaps,
        key=lambda g: len([m for m in g.missing if m != "friction"]),
        reverse=True,
    )
    return ranked[0] if ranked else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_coverage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/coverage.py tests/praxis/test_coverage.py
git commit -m "feat(praxis): deterministic coverage analysis for probing + scoring"
```

---

## Task 4: Discovery extraction (message → grounded graph deltas)

**Files:**
- Create: `praxis/discovery_prompts.py`
- Create: `praxis/discovery.py`
- Test: `tests/praxis/test_discovery_extract.py`

**Interfaces:**
- Consumes: `OllamaClient` (Task 2), `WorkflowModel`/types (Task 1).
- Produces:
  - In `discovery_prompts.py`: `EXTRACTION_SYSTEM: str` and `build_extraction_user(history: list[dict], latest: str) -> str`.
  - In `discovery.py`:
    - `async extract_deltas(client, history: list[dict], latest_msg: str, turn: int) -> list[dict]` — returns delta dicts shaped `{"op":"add_node","node_type":..,"label":..,"quote":..}` or `{"op":"add_edge","edge_type":..,"source_label":..,"source_type":..,"target_label":..,"target_type":..,"quote":..}`. **Deltas whose `quote` is missing/empty are dropped here** (evidence-required).
    - `apply_deltas(model: WorkflowModel, deltas: list[dict], turn: int) -> None` — mutates model, reusing existing nodes by (label,type), creating them if absent; skips edges whose endpoints can't be resolved.

- [ ] **Step 1: Write the failing test** (faked client — no real Ollama in unit tests)

```python
# tests/praxis/test_discovery_extract.py
import pytest
from praxis.models import WorkflowModel, NodeType
from praxis.discovery import extract_deltas, apply_deltas

class FakeClient:
    def __init__(self, payload): self.payload = payload
    async def complete_json(self, system, user, **kw): return self.payload

@pytest.mark.asyncio
async def test_extract_drops_evidenceless_deltas():
    payload = {"deltas": [
        {"op": "add_node", "node_type": "step", "label": "send quote", "quote": "then I send them a quote"},
        {"op": "add_node", "node_type": "step", "label": "hallucinated step", "quote": ""},
    ]}
    deltas = await extract_deltas(FakeClient(payload), [], "then I send them a quote", turn=1)
    labels = [d["label"] for d in deltas]
    assert "send quote" in labels
    assert "hallucinated step" not in labels  # evidence-required drop

@pytest.mark.asyncio
async def test_apply_deltas_reuses_nodes_and_links_edges():
    m = WorkflowModel()
    deltas = [
        {"op": "add_node", "node_type": "actor", "label": "me", "quote": "I do it"},
        {"op": "add_node", "node_type": "step", "label": "send quote", "quote": "I send a quote"},
        {"op": "add_edge", "edge_type": "performs",
         "source_label": "me", "source_type": "actor",
         "target_label": "send quote", "target_type": "step", "quote": "I send a quote"},
    ]
    apply_deltas(m, deltas, turn=1)
    assert m.find_node("me", NodeType.ACTOR) is not None
    assert len(m.edges) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.discovery'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/discovery_prompts.py
"""From-scratch Discovery prompts. Voice: a sharp, personable operator who has
walked a hundred shop floors — brisk, curious, NOT therapeutic. Written fresh for
business-workflow interviews; do not port wellness prompt text (Global Constraint)."""
import json

EXTRACTION_SYSTEM = """You extract a business's workflow into a graph, using ONLY the \
person's own words as evidence. Never invent steps, tools, or people they did not mention.

Return JSON: {"deltas": [ ... ]}. Each delta is one of:
- {"op":"add_node","node_type":"step|actor|tool|artifact|friction","label":"<short, their words>","quote":"<the exact phrase that justifies it>"}
- {"op":"add_edge","edge_type":"sequence|performs|uses|produces|consumes|causes","source_label":"..","source_type":"..","target_label":"..","target_type":"..","quote":"<exact phrase>"}

Rules:
- Every delta MUST include a verbatim quote from the latest message. No quote -> do not emit it.
- Labels are short and in the speaker's vocabulary (e.g. "the order sheet", not "Order Management System").
- Only extract what THIS message adds. Do not restate the whole graph."""


def build_extraction_user(history, latest):
    recent = "\n".join(f'{m["role"]}: {m["content"]}' for m in history[-6:])
    return json.dumps({"recent_conversation": recent, "latest_client_message": latest}, indent=2)
```

```python
# praxis/discovery.py
"""Discovery agent operations: extract grounded graph deltas from a client turn,
apply them to the WorkflowModel, and ask the next gap-driven question."""
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P

_VALID_NODE = {t.value for t in NodeType}
_VALID_EDGE = {t.value for t in EdgeType}


async def extract_deltas(client, history, latest_msg, turn):
    result = await client.complete_json(P.EXTRACTION_SYSTEM,
                                        P.build_extraction_user(history, latest_msg))
    out = []
    for d in result.get("deltas", []):
        quote = (d.get("quote") or "").strip()
        if not quote:
            continue  # evidence-required: drop
        if d.get("op") == "add_node" and d.get("node_type") in _VALID_NODE and d.get("label"):
            out.append(d)
        elif d.get("op") == "add_edge" and d.get("edge_type") in _VALID_EDGE \
                and d.get("source_label") and d.get("target_label"):
            out.append(d)
    return out


def _get_or_add(model, label, ntype, ev):
    existing = model.find_node(label, ntype)
    if existing:
        existing.evidence.append(ev)
        existing.confidence.evidence_count += 1
        return existing
    return model.add_node(ntype, label, [ev])


def apply_deltas(model, deltas, turn):
    for d in deltas:
        ev = Evidence(d["quote"].strip(), turn)
        if d["op"] == "add_node":
            _get_or_add(model, d["label"], NodeType(d["node_type"]), ev)
    for d in deltas:  # edges after nodes so endpoints resolve
        if d["op"] != "add_edge":
            continue
        ev = Evidence(d["quote"].strip(), turn)
        src = _get_or_add(model, d["source_label"], NodeType(d["source_type"]), ev)
        tgt = _get_or_add(model, d["target_label"], NodeType(d["target_type"]), ev)
        model.add_edge(EdgeType(d["edge_type"]), src.id, tgt.id, [ev])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_extract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/discovery_prompts.py praxis/discovery.py tests/praxis/test_discovery_extract.py
git commit -m "feat(praxis): Discovery extraction with evidence-required grounding"
```

---

## Task 5: Discovery interviewer (gap-driven next question)

**Files:**
- Modify: `praxis/discovery_prompts.py` (add interviewer prompt)
- Modify: `praxis/discovery.py` (add `next_question`)
- Test: `tests/praxis/test_discovery_question.py`

**Interfaces:**
- Consumes: `OllamaClient` (Task 2), `analyze_coverage`/`biggest_gap` (Task 3), `WorkflowModel` (Task 1).
- Produces:
  - `INTERVIEWER_SYSTEM: str`, `build_interviewer_user(history, focus_hint: str) -> str` in prompts.
  - `async next_question(client, model: WorkflowModel, history: list[dict]) -> str` in `discovery.py` — computes coverage, turns the biggest gap (or a thin/orphan area) into a `focus_hint`, and asks the model for ONE natural question. Returns the question text.
  - `focus_hint_for(model) -> str` (pure helper, testable without the LLM): e.g. `"For the step 'file it', find out: who does it, what tool they use."` or, if no gaps, `"Ask what happens right after the last step, or what part of this work is most painful."`

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_discovery_question.py
import pytest
from praxis.models import WorkflowModel, NodeType, Evidence
from praxis.discovery import next_question, focus_hint_for

def test_focus_hint_targets_the_biggest_gap():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "file it", [Evidence("then we file it", 1)])
    hint = focus_hint_for(m)
    assert "file it" in hint
    assert "who" in hint.lower()

def test_focus_hint_when_no_gaps_asks_sequence_or_pain():
    hint = focus_hint_for(WorkflowModel())
    assert "painful" in hint.lower() or "after" in hint.lower()

class FakeClient:
    def __init__(self): self.last_user = None
    async def complete(self, system, messages, **kw):
        self.last_user = messages[-1]["content"]
        return "Who actually files it, and what do they file it in?"

@pytest.mark.asyncio
async def test_next_question_passes_focus_to_model():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "file it", [Evidence("then we file it", 1)])
    fc = FakeClient()
    q = await next_question(fc, m, [{"role": "user", "content": "then we file it"}])
    assert "file it" in fc.last_user       # focus hint reached the model
    assert q.endswith("?")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_question.py -v`
Expected: FAIL — `ImportError: cannot import name 'next_question'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to praxis/discovery_prompts.py
INTERVIEWER_SYSTEM = """You are Praxis's discovery lead: a sharp, warm operator mapping \
how a business actually works. You are talking to a business owner or worker who is NOT \
technical and may be vague. Ask ONE concrete, plain-language question at a time. Never \
therapize, never lecture, never dump a list. Use their words back to them. Your goal is to \
fill the specific gap you're told about, or — if none — to trace what happens next or find \
the most painful part."""


def build_interviewer_user(history, focus_hint):
    recent = "\n".join(f'{m["role"]}: {m["content"]}' for m in history[-6:])
    return f"Conversation so far:\n{recent}\n\nYour focus right now: {focus_hint}\n\nAsk one question."
```

```python
# add to praxis/discovery.py
from praxis.coverage import analyze_coverage, biggest_gap

_FACET_Q = {
    "actor": "who does it", "tool": "what tool they use",
    "input": "what they start with", "output": "what it produces",
    "friction": "what goes wrong there",
}


def focus_hint_for(model):
    rep = analyze_coverage(model)
    gap = biggest_gap(rep)
    if gap:
        wants = ", ".join(_FACET_Q[f] for f in gap.missing if f in _FACET_Q)
        return f"For the step '{gap.step_label}', find out: {wants}."
    return "Ask what happens right after the last step, or what part of this work is most painful."


async def next_question(client, model, history):
    hint = focus_hint_for(model)
    system = P.INTERVIEWER_SYSTEM
    user = P.build_interviewer_user(history, hint)
    text = await client.complete(system, [{"role": "user", "content": user}],
                                 max_tokens=120, temperature=0.7)
    return text.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_discovery_question.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/discovery_prompts.py praxis/discovery.py tests/praxis/test_discovery_question.py
git commit -m "feat(praxis): gap-driven Discovery questioning"
```

---

## Task 6: DiscoverySession loop + completeness

**Files:**
- Create: `praxis/session.py`
- Test: `tests/praxis/test_session.py`

**Interfaces:**
- Consumes: `extract_deltas`, `apply_deltas`, `next_question` (Tasks 4–5), `analyze_coverage` (Task 3), `WorkflowModel` (Task 1).
- Produces:
  - `class DiscoverySession(client, max_turns=25, coverage_target=0.8)` with:
    - `model: WorkflowModel`, `history: list[dict]`, `turn: int`
    - `async submit(client_message: str) -> str` — extract+apply the client's message, then return the next question (or the closing line if complete).
    - `is_intake_complete() -> bool` — True when `analyze_coverage(model).overall >= coverage_target` with ≥2 steps, OR `turn >= max_turns`.
    - `opening_line() -> str` (static-ish greeting to start the interview).
  - Reason completeness lives here, not in Discovery: the session owns the stop condition (Spec §4 "how the firm knows intake is done").

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_session.py
import pytest
from praxis.session import DiscoverySession
from praxis.models import NodeType

class ScriptedClient:
    """Fakes both extraction (returns queued deltas) and questioning (echoes)."""
    def __init__(self, delta_script):
        self.delta_script = list(delta_script)
    async def complete_json(self, system, user, **kw):
        return self.delta_script.pop(0) if self.delta_script else {"deltas": []}
    async def complete(self, system, messages, **kw):
        return "And what happens next?"

@pytest.mark.asyncio
async def test_session_builds_model_and_reaches_completion():
    script = [
        {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "take order", "quote": "I take the order"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "I take the order"},
            {"op": "add_node", "node_type": "tool", "label": "notebook", "quote": "in my notebook"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "take order", "target_type": "step", "quote": "I take the order"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "take order", "source_type": "step",
             "target_label": "notebook", "target_type": "tool", "quote": "in my notebook"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "take order", "source_type": "step",
             "target_label": "order slip", "target_type": "artifact", "quote": "I take the order"},
        ]},
    ]
    s = DiscoverySession(ScriptedClient(script), coverage_target=0.5)
    reply = await s.submit("I take the order in my notebook")
    assert s.model.find_node("take order", NodeType.STEP) is not None
    assert isinstance(reply, str) and len(reply) > 0

@pytest.mark.asyncio
async def test_session_stops_at_max_turns():
    s = DiscoverySession(ScriptedClient([]), max_turns=1)
    await s.submit("uh, we do stuff")
    assert s.is_intake_complete() is True  # hit the turn cap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.session'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/session.py
"""Drives one Discovery interview: client message -> grow graph -> next question,
until coverage is high enough or the turn cap is hit. The session owns the stop
condition (intake-completeness)."""
from praxis.models import WorkflowModel, NodeType
from praxis.coverage import analyze_coverage
from praxis.discovery import extract_deltas, apply_deltas, next_question

OPENING = ("Thanks for making the time. In your own words, walk me through what you "
           "actually do day to day — start wherever the work starts.")
CLOSING = ("That gives me a solid picture. I'll take it from here and map it out.")


class DiscoverySession:
    def __init__(self, client, max_turns=25, coverage_target=0.8):
        self.client = client
        self.max_turns = max_turns
        self.coverage_target = coverage_target
        self.model = WorkflowModel()
        self.history = []
        self.turn = 0

    def opening_line(self):
        return OPENING

    def is_intake_complete(self):
        if self.turn >= self.max_turns:
            return True
        rep = analyze_coverage(self.model)
        return len(self.model.nodes_of(NodeType.STEP)) >= 2 and rep.overall >= self.coverage_target

    async def submit(self, client_message):
        self.turn += 1
        self.history.append({"role": "user", "content": client_message})
        deltas = await extract_deltas(self.client, self.history, client_message, self.turn)
        apply_deltas(self.model, deltas, self.turn)
        if self.is_intake_complete():
            self.history.append({"role": "assistant", "content": CLOSING})
            return CLOSING
        q = await next_question(self.client, self.model, self.history)
        self.history.append({"role": "assistant", "content": q})
        return q
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_session.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/session.py tests/praxis/test_session.py
git commit -m "feat(praxis): DiscoverySession loop with intake-completeness gate"
```

---

## Task 7: Difficult-client scenarios + simulator

**Files:**
- Create: `praxis/eval/__init__.py` (empty)
- Create: `praxis/eval/scenarios.py`
- Create: `praxis/eval/client_sim.py`
- Test: `tests/praxis/test_client_sim.py`

**Interfaces:**
- Consumes: `OllamaClient` (Task 2).
- Produces:
  - `scenarios.py`: `@dataclass Scenario(key: str, business: str, persona: str, truth: str)` and `SCENARIOS: list[Scenario]` with at least four hard cases: `vague_baker`, `rambling_agency`, `jargon_manufacturer`, `defensive_founder`. `persona` describes HOW they answer (brief/rambling/jargon/guarded); `truth` is the real workflow they'll reveal if asked well (so runs are comparable).
  - `client_sim.py`: `SIM_SYSTEM(scenario) -> str` and `async simulated_reply(client, scenario, interviewer_question, history) -> str` — the LLM role-plays the client answering the interviewer, staying in persona and only revealing `truth` details when actually asked.

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_client_sim.py
import pytest
from praxis.eval.scenarios import SCENARIOS, Scenario
from praxis.eval.client_sim import simulated_reply

def test_scenarios_are_well_formed():
    keys = {s.key for s in SCENARIOS}
    assert {"vague_baker", "rambling_agency", "jargon_manufacturer", "defensive_founder"} <= keys
    for s in SCENARIOS:
        assert s.business and s.persona and s.truth

class FakeClient:
    def __init__(self): self.saw = None
    async def complete(self, system, messages, **kw):
        self.saw = system
        return "I dunno, we just kind of get the orders done."

@pytest.mark.asyncio
async def test_simulated_reply_uses_persona_system():
    fc = FakeClient()
    sc = SCENARIOS[0]
    out = await simulated_reply(fc, sc, "Walk me through your day.", [])
    assert sc.persona[:12] in fc.saw   # persona injected into the sim's system prompt
    assert isinstance(out, str) and out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_client_sim.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.eval'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/eval/scenarios.py
"""Hard, non-expert client personas for the Phase 0 gate. These are deliberately
difficult (vague, rambling, jargon-heavy, defensive) — the point is to stress
Discovery, not to hand it cooperative interviews."""
from dataclasses import dataclass


@dataclass
class Scenario:
    key: str
    business: str
    persona: str
    truth: str


SCENARIOS = [
    Scenario(
        key="vague_baker",
        business="a two-person neighborhood bakery",
        persona="brief and vague; gives three-word answers; assumes you already know how bakeries work; rarely volunteers detail unless asked a pointed question",
        truth="Orders come in by phone and a paper notebook; baker bakes from the notebook list each morning; spouse handles pickups and takes cash; leftover count is guessed and often wrong; ingredient reordering is done from memory when a shelf looks empty.",
    ),
    Scenario(
        key="rambling_agency",
        business="a small marketing agency",
        persona="rambles, tells stories, jumps between topics, over-explains the backstory before answering; friendly but hard to pin down",
        truth="Leads arrive via a web form into email; an account manager copies them into a spreadsheet; proposals are written in Google Docs from a rough template; invoicing is manual in QuickBooks; project status lives in people's heads and Slack threads.",
    ),
    Scenario(
        key="jargon_manufacturer",
        business="a small custom-parts machine shop",
        persona="answers in shop jargon and acronyms without explaining them; terse; assumes you know the trade",
        truth="Quotes come from emailed drawings; the owner estimates by hand; jobs get a paper traveler that follows the part; machinists log hours on a clipboard; finished parts are QC'd visually; shipping paperwork is retyped into the accounting system.",
    ),
    Scenario(
        key="defensive_founder",
        business="a subscription box startup",
        persona="guarded and a little suspicious of the interview; short answers; needs a reason before sharing; warms up only if the questions are concrete and respectful",
        truth="Signups hit Stripe; a founder exports CSVs weekly; fulfillment list is pasted into a 3PL portal; customer emails are handled in a shared inbox; churn is tracked in a spreadsheet updated when someone remembers.",
    ),
]
```

```python
# praxis/eval/client_sim.py
"""LLM role-play of a scenario client, so Phase 0 can run repeatable hard interviews
without recruiting real humans."""


def SIM_SYSTEM(scenario):
    return (
        f"You are the owner of {scenario.business}. Stay fully in character.\n"
        f"How you answer: {scenario.persona}.\n"
        f"The real workflow (reveal ONLY the specific bits you're actually asked about, "
        f"in your own casual words, never as a tidy list): {scenario.truth}\n"
        f"Answer in 1-3 sentences. Never break character or explain that you are an AI."
    )


async def simulated_reply(client, scenario, interviewer_question, history):
    msgs = []
    for h in history[-6:]:
        msgs.append(h)
    msgs.append({"role": "user", "content": interviewer_question})
    return (await client.complete(SIM_SYSTEM(scenario), msgs,
                                  max_tokens=160, temperature=0.9)).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_client_sim.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/eval/__init__.py praxis/eval/scenarios.py praxis/eval/client_sim.py tests/praxis/test_client_sim.py
git commit -m "feat(praxis): hard-client scenarios + LLM client simulator for Phase 0"
```

---

## Task 8: Eval harness (run Discovery vs a simulated client, persist artifacts + cost)

**Files:**
- Create: `praxis/eval/harness.py`
- Test: `tests/praxis/test_harness.py`

**Interfaces:**
- Consumes: `DiscoverySession` (Task 6), `simulated_reply`+`SCENARIOS` (Task 7), `WorkflowModel` (Task 1).
- Produces:
  - `@dataclass RunResult(scenario_key, transcript: list[dict], model_dict: dict, turns: int, seconds: float)`
  - `async run_scenario(interviewer_client, client_sim_client, scenario, clock, max_turns=25) -> RunResult` — alternates `session.submit(client_reply)` and `simulated_reply(...)` until `session.is_intake_complete()`. `clock` is a zero-arg callable returning seconds (injected so tests are deterministic and the script stays offline-pure).
  - `save_run(result: RunResult, out_dir: str) -> str` — writes `<out_dir>/<scenario_key>.json` (transcript + graph + metrics), returns the path.

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_harness.py
import json, pytest
from praxis.eval.scenarios import Scenario
from praxis.eval.harness import run_scenario, save_run

class InterviewerStub:
    async def complete_json(self, system, user, **kw):
        return {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "do the thing", "quote": "we do the thing"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "we do the thing"},
            {"op": "add_node", "node_type": "tool", "label": "sheet", "quote": "in a sheet"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "do the thing", "target_type": "step", "quote": "we do the thing"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "do the thing", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "in a sheet"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "do the thing", "source_type": "step",
             "target_label": "result", "target_type": "artifact", "quote": "we do the thing"},
        ]}
    async def complete(self, system, messages, **kw):
        return "What happens next?"

class SimStub:
    async def complete(self, system, messages, **kw):
        return "We do the thing in a sheet."

@pytest.mark.asyncio
async def test_run_scenario_and_save(tmp_path):
    sc = Scenario("t", "a test biz", "brief", "they do the thing in a sheet")
    ticks = iter([0.0, 4.2])
    res = await run_scenario(InterviewerStub(), SimStub(), sc,
                             clock=lambda: next(ticks), max_turns=5)
    assert res.turns >= 1
    assert res.seconds == 4.2
    path = save_run(res, str(tmp_path))
    saved = json.loads(open(path).read())
    assert saved["scenario_key"] == "t"
    assert saved["metrics"]["seconds"] == 4.2
    assert "nodes" in saved["model"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_harness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.eval.harness'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/eval/harness.py
"""Run one Discovery interview against a simulated client and persist everything the
Phase 0 gate needs to judge it: transcript, graph, turns, wall-clock."""
import json
import os
from dataclasses import dataclass, field
from praxis.session import DiscoverySession
from praxis.eval.client_sim import simulated_reply


@dataclass
class RunResult:
    scenario_key: str
    transcript: list = field(default_factory=list)
    model_dict: dict = field(default_factory=dict)
    turns: int = 0
    seconds: float = 0.0


async def run_scenario(interviewer_client, client_sim_client, scenario, clock, max_turns=25):
    session = DiscoverySession(interviewer_client, max_turns=max_turns)
    start = clock()
    interviewer_line = session.opening_line()
    sim_history = []
    while not session.is_intake_complete():
        client_msg = await simulated_reply(client_sim_client, scenario, interviewer_line, sim_history)
        sim_history.append({"role": "user", "content": interviewer_line})
        sim_history.append({"role": "assistant", "content": client_msg})
        interviewer_line = await session.submit(client_msg)
    seconds = clock() - start
    return RunResult(
        scenario_key=scenario.key,
        transcript=session.history,
        model_dict=session.model.to_dict(),
        turns=session.turn,
        seconds=seconds,
    )


def save_run(result: RunResult, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{result.scenario_key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario_key": result.scenario_key,
            "transcript": result.transcript,
            "model": result.model_dict,
            "metrics": {"turns": result.turns, "seconds": result.seconds},
        }, f, indent=2)
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_harness.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/eval/harness.py tests/praxis/test_harness.py
git commit -m "feat(praxis): Phase 0 eval harness — run + persist Discovery interviews"
```

---

## Task 9: Scoring — automated structural checks + human-rubric scorecard + gate report

**Files:**
- Create: `praxis/eval/scoring.py`
- Test: `tests/praxis/test_scoring.py`

**Interfaces:**
- Consumes: `WorkflowModel` (Task 1), `analyze_coverage` (Task 3), `RunResult`/saved JSON (Task 8).
- Produces:
  - `structural_score(model_dict: dict) -> dict` → `{"connected": bool, "grounded": bool, "grain_ok": bool, "coverage": float, "orphans": int, "evidenceless": int, "grain_outliers": int}`. `connected` = no orphan steps; `grounded` = zero evidenceless; `grain_ok` = zero grain outliers.
  - `RUBRIC_FIELDS: list[str]` = the human-scored dimensions (`"adapted_to_them"`, `"honest_about_gaps"`, `"would_help"`), each scored 1–5 by a human reviewer.
  - `blank_scorecard(scenario_key) -> dict` — merges auto fields + empty human-rubric fields for a reviewer to fill.
  - `gate_report(scorecards: list[dict]) -> dict` → `{"n": int, "auto_pass_rate": float, "avg_coverage": float, "avg_seconds": float | None, "human_pending": int, "verdict_hint": str}`. `auto_pass` for a run = connected & grounded & grain_ok & coverage ≥ 0.8. `verdict_hint` is `"AUTO-PASS majority; awaiting human scores"` / `"AUTO-FAIL — Discovery not reliable"` (majority auto-fail) / `"MIXED"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/praxis/test_scoring.py
from praxis.eval.scoring import structural_score, blank_scorecard, gate_report, RUBRIC_FIELDS

GOOD = {
    "nodes": [
        {"id": "n1", "type": "step", "label": "take order", "evidence": [{"quote": "I take the order", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "n2", "type": "actor", "label": "me", "evidence": [{"quote": "I take the order", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "n3", "type": "tool", "label": "notebook", "evidence": [{"quote": "in my notebook", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "n4", "type": "artifact", "label": "slip", "evidence": [{"quote": "a slip", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
    ],
    "edges": [
        {"id": "e1", "type": "performs", "source": "n2", "target": "n1", "evidence": [{"quote": "I take the order", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "e2", "type": "uses", "source": "n1", "target": "n3", "evidence": [{"quote": "in my notebook", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "e3", "type": "produces", "source": "n1", "target": "n4", "evidence": [{"quote": "a slip", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
    ],
}

def test_structural_score_on_good_model():
    s = structural_score(GOOD)
    assert s["connected"] and s["grounded"] and s["grain_ok"]
    assert s["coverage"] == 1.0

def test_blank_scorecard_has_human_fields():
    card = blank_scorecard("vague_baker")
    for f in RUBRIC_FIELDS:
        assert card["human"][f] is None

def test_gate_report_flags_auto_pass_majority():
    cards = [blank_scorecard("a"), blank_scorecard("b")]
    for c in cards:
        c["auto"] = structural_score(GOOD)
        c["auto"]["seconds"] = 30.0
    rep = gate_report(cards)
    assert rep["n"] == 2
    assert rep["auto_pass_rate"] == 1.0
    assert "AUTO-PASS" in rep["verdict_hint"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.eval.scoring'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/eval/scoring.py
"""Phase 0 scoring. Automated structural checks are deterministic pass/fail;
the deeper quality dimensions are left for a human reviewer (Spec §7: no faked
quality oracle). gate_report aggregates against the Phase 0 pass criteria (Spec §8)."""
from praxis.models import WorkflowModel
from praxis.coverage import analyze_coverage

RUBRIC_FIELDS = ["adapted_to_them", "honest_about_gaps", "would_help"]
COVERAGE_BAR = 0.8


def structural_score(model_dict: dict) -> dict:
    model = WorkflowModel.from_dict(model_dict)
    rep = analyze_coverage(model)
    return {
        "connected": len(rep.orphan_steps) == 0,
        "grounded": len(rep.evidenceless) == 0,
        "grain_ok": len(rep.grain_outliers) == 0,
        "coverage": rep.overall,
        "orphans": len(rep.orphan_steps),
        "evidenceless": len(rep.evidenceless),
        "grain_outliers": len(rep.grain_outliers),
    }


def blank_scorecard(scenario_key: str) -> dict:
    return {
        "scenario_key": scenario_key,
        "auto": {},
        "human": {f: None for f in RUBRIC_FIELDS},  # reviewer fills 1-5
    }


def _auto_pass(auto: dict) -> bool:
    return bool(auto.get("connected") and auto.get("grounded")
               and auto.get("grain_ok") and auto.get("coverage", 0) >= COVERAGE_BAR)


def gate_report(scorecards: list) -> dict:
    n = len(scorecards)
    autos = [c.get("auto", {}) for c in scorecards]
    passes = [a for a in autos if _auto_pass(a)]
    secs = [a["seconds"] for a in autos if "seconds" in a]
    human_pending = sum(1 for c in scorecards
                        if any(c["human"][f] is None for f in RUBRIC_FIELDS))
    pass_rate = (len(passes) / n) if n else 0.0
    if pass_rate > 0.5:
        hint = "AUTO-PASS majority; awaiting human scores"
    elif pass_rate < 0.5:
        hint = "AUTO-FAIL — Discovery not reliable; change approach before building downstream"
    else:
        hint = "MIXED"
    return {
        "n": n,
        "auto_pass_rate": pass_rate,
        "avg_coverage": (sum(a.get("coverage", 0) for a in autos) / n) if n else 0.0,
        "avg_seconds": (sum(secs) / len(secs)) if secs else None,
        "human_pending": human_pending,
        "verdict_hint": hint,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add praxis/eval/scoring.py tests/praxis/test_scoring.py
git commit -m "feat(praxis): Phase 0 scoring — structural checks + human rubric + gate report"
```

---

## Task 10: Phase 0 runner CLI (live, against Ollama)

**Files:**
- Create: `praxis/eval/run_phase0.py`
- Create: `praxis/cli.py`
- Test: `tests/praxis/test_run_phase0.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `praxis/eval/run_phase0.py`: `async main(out_dir="phase0_out", scenario_keys=None) -> dict` — for each scenario, run `run_scenario` with a real `OllamaClient` for both interviewer and client-sim (separate instances), `clock=time.monotonic`, `save_run`, build a scorecard (`blank_scorecard` + `structural_score`, attach `seconds`), write `scorecards.json` and `gate_report.json`; return the gate report. Guarded by `if __name__ == "__main__": asyncio.run(main())`.
  - `praxis/cli.py`: `async chat()` — a live terminal Discovery interview: print `opening_line()`, read stdin, `session.submit`, print the question, loop until `is_intake_complete()`, then dump the graph JSON. `if __name__ == "__main__": asyncio.run(chat())`.
- Note: `time` and `asyncio` imports live inside these entry-point modules only (Global Constraint forbids `Date.now()`-style calls inside pure logic, but these are top-level scripts, not workflow scripts — real wall-clock is required here to measure cost).

- [ ] **Step 1: Write the failing test** (inject stubs so the test stays offline)

```python
# tests/praxis/test_run_phase0.py
import json, pytest
import praxis.eval.run_phase0 as r0
from praxis.eval.scenarios import Scenario

class InterviewerStub:
    async def complete_json(self, system, user, **kw):
        return {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "do it", "quote": "we do it"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "we do it"},
            {"op": "add_node", "node_type": "tool", "label": "sheet", "quote": "a sheet"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "do it", "target_type": "step", "quote": "we do it"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "do it", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "a sheet"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "do it", "source_type": "step",
             "target_label": "out", "target_type": "artifact", "quote": "we do it"},
        ]}
    async def complete(self, system, messages, **kw): return "Next?"
    async def close(self): pass

class SimStub:
    async def complete(self, system, messages, **kw): return "We do it in a sheet."
    async def close(self): pass

@pytest.mark.asyncio
async def test_main_writes_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(r0, "_make_client", lambda: InterviewerStub())
    monkeypatch.setattr(r0, "_make_sim_client", lambda: SimStub())
    monkeypatch.setattr(r0, "SCENARIOS", [Scenario("solo", "biz", "brief", "they do it in a sheet")])
    rep = await r0.main(out_dir=str(tmp_path))
    assert (tmp_path / "gate_report.json").exists()
    assert (tmp_path / "scorecards.json").exists()
    assert rep["n"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_run_phase0.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'praxis.eval.run_phase0'`

- [ ] **Step 3: Write minimal implementation**

```python
# praxis/eval/run_phase0.py
"""Phase 0 gate runner. Runs Discovery against every hard-client scenario on real
local Ollama, persists artifacts, and emits the gate report. This is the script whose
output decides whether we build the rest of the firm (Spec §8)."""
import asyncio
import json
import os
import time
from praxis.llm_client import OllamaClient
from praxis.eval.scenarios import SCENARIOS
from praxis.eval.harness import run_scenario, save_run
from praxis.eval.scoring import blank_scorecard, structural_score, gate_report


def _make_client():
    return OllamaClient()


def _make_sim_client():
    return OllamaClient()


async def main(out_dir="phase0_out", scenario_keys=None):
    os.makedirs(out_dir, exist_ok=True)
    scenarios = [s for s in SCENARIOS if (scenario_keys is None or s.key in scenario_keys)]
    interviewer = _make_client()
    sim = _make_sim_client()
    scorecards = []
    try:
        for sc in scenarios:
            result = await run_scenario(interviewer, sim, sc, clock=time.monotonic)
            save_run(result, out_dir)
            card = blank_scorecard(sc.key)
            card["auto"] = structural_score(result.model_dict)
            card["auto"]["seconds"] = result.seconds
            card["auto"]["turns"] = result.turns
            scorecards.append(card)
    finally:
        await interviewer.close()
        await sim.close()

    report = gate_report(scorecards)
    with open(os.path.join(out_dir, "scorecards.json"), "w", encoding="utf-8") as f:
        json.dump(scorecards, f, indent=2)
    with open(os.path.join(out_dir, "gate_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    asyncio.run(main())
```

```python
# praxis/cli.py
"""Live terminal Discovery interview against local Ollama. For eyeballing the real
interaction — the human check the eval harness can't replace."""
import asyncio
import json
from praxis.llm_client import OllamaClient
from praxis.session import DiscoverySession


async def chat():
    client = OllamaClient()
    session = DiscoverySession(client)
    print("PRAXIS >", session.opening_line())
    try:
        while not session.is_intake_complete():
            msg = input("you   > ").strip()
            if msg.lower() in {"quit", "exit"}:
                break
            reply = await session.submit(msg)
            print("PRAXIS >", reply)
    finally:
        await client.close()
    print("\n--- WORKFLOW MAP ---")
    print(json.dumps(session.model.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(chat())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/test_run_phase0.py -v`
Expected: PASS

- [ ] **Step 5: Run the full praxis suite and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/praxis/ -v`
Expected: all PASS

```bash
git add praxis/eval/run_phase0.py praxis/cli.py tests/praxis/test_run_phase0.py
git commit -m "feat(praxis): Phase 0 live runner + terminal Discovery CLI"
```

---

## Task 11: Run the gate for real + record the verdict

This task has no automated test — it is the actual Phase 0 experiment. Follow the anti-confirmation discipline (Spec §8): criteria are already fixed above; run it to falsify.

- [ ] **Step 1: Confirm Ollama is up with the model**

Run: `ollama list` (expect `qwen3.5:9b` present; if not, `ollama pull qwen3.5:9b`).

- [ ] **Step 2: Run the gate**

Run: `.venv\Scripts\python.exe -m praxis.eval.run_phase0`
Expected: `phase0_out/` contains one JSON per scenario, `scorecards.json`, `gate_report.json`; the report prints.

- [ ] **Step 3: Eyeball two transcripts**

Open `phase0_out/vague_baker.json` and `phase0_out/defensive_founder.json`. Read the transcript. Does the interviewer stay concrete and non-therapeutic? Does the graph match what the client actually said?

- [ ] **Step 4: Human-score each run**

For each scorecard in `phase0_out/scorecards.json`, a skeptical reviewer (ideally not the prompt author) fills `human.adapted_to_them`, `human.honest_about_gaps`, `human.would_help` (1–5). Re-run `gate_report` over the filled scorecards (or compute by hand).

- [ ] **Step 5: Record the verdict against the pre-committed criteria**

Write `phase0_out/VERDICT.md`: auto-pass rate, avg coverage, avg seconds/interview, human averages, and the go/no-go call. If it FAILS, pick a pre-committed failure branch (operator co-pilot / narrow scope / simplify roster) — do not proceed to downstream agents. Commit the verdict:

```bash
git add phase0_out/VERDICT.md
git commit -m "chore(praxis): record Phase 0 gate verdict"
```

---

## Out of scope (built only if Phase 0 passes)

Downstream milestones, each its own plan: Analyst → Architect → Business-case → Skeptic → Principal; the deliverable renderer + honesty sections; the six-agent-vs-baseline comparison (Spec §8); SQLite persistence (`praxis.db`); the FastAPI/web UI; the operator graph-review checkpoint UI (supervision valve); and all of Sub-project 2 (the Build Wing).
