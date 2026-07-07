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

def test_overall_is_exact_fraction():
    m = WorkflowModel()
    s1 = m.add_node(NodeType.STEP, "s1", _ev())
    a = m.add_node(NodeType.ACTOR, "a", _ev())
    t = m.add_node(NodeType.TOOL, "t", _ev())
    art = m.add_node(NodeType.ARTIFACT, "art", _ev())
    m.add_edge(EdgeType.PERFORMS, a.id, s1.id, _ev())
    m.add_edge(EdgeType.USES, s1.id, t.id, _ev())
    m.add_edge(EdgeType.PRODUCES, s1.id, art.id, _ev())
    m.add_node(NodeType.STEP, "s2", _ev())  # orphan, unsatisfied
    rep = analyze_coverage(m)
    assert rep.overall == 0.5   # 1 of 2 steps satisfied

def test_friction_only_step_is_reported_but_not_hard_gap():
    m = WorkflowModel()
    s1 = m.add_node(NodeType.STEP, "s1", _ev())
    a = m.add_node(NodeType.ACTOR, "a", _ev())
    t = m.add_node(NodeType.TOOL, "t", _ev())
    inp = m.add_node(NodeType.ARTIFACT, "in", _ev())
    out = m.add_node(NodeType.ARTIFACT, "out", _ev())
    m.add_edge(EdgeType.PERFORMS, a.id, s1.id, _ev())
    m.add_edge(EdgeType.USES, s1.id, t.id, _ev())
    m.add_edge(EdgeType.CONSUMES, s1.id, inp.id, _ev())
    m.add_edge(EdgeType.PRODUCES, s1.id, out.id, _ev())
    rep = analyze_coverage(m)
    assert rep.overall == 1.0                       # friction absence does not depress coverage
    gaps = [g for g in rep.step_gaps if g.step_id == s1.id]
    assert gaps and gaps[0].missing == ["friction"] # reported, but only friction
    assert biggest_gap(rep).step_id == s1.id        # still returned; ranked by 0 non-friction gaps

def test_biggest_gap_tie_breaks_to_first():
    m = WorkflowModel()
    a = m.add_node(NodeType.ACTOR, "a", _ev())
    s1 = m.add_node(NodeType.STEP, "s1", _ev())
    s2 = m.add_node(NodeType.STEP, "s2", _ev())
    m.add_edge(EdgeType.PERFORMS, a.id, s1.id, _ev())
    m.add_edge(EdgeType.PERFORMS, a.id, s2.id, _ev())
    rep = analyze_coverage(m)  # both miss tool+input+output equally
    assert biggest_gap(rep).step_id == s1.id  # tie -> first inserted

def test_empty_model_overall_is_zero():
    rep = analyze_coverage(WorkflowModel())
    assert rep.overall == 0.0
