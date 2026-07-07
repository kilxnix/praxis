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
