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
