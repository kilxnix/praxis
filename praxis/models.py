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
