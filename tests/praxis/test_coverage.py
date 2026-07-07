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
