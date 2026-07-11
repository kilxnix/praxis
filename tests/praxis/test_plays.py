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


def test_probed_foci_stops_reasking_same_facet():
    """Once a facet has been asked, complete_step_facets must not re-target it — the discovery
    loop that re-asked 're-type into contract?' four times."""
    from praxis.plays import _nonfriction_gap, focus_target
    m = WorkflowModel()
    s = m.add_node(NodeType.STEP, "chat about vibe", _ev())
    # Unsatisfied: no actor, no tool/input/output
    st = InterviewState(m, last_answer="we chat about vibe")
    g1 = _nonfriction_gap(st)
    assert g1 is not None
    facet1 = g1[1][0]
    st.probed_foci.add(st.focus_key(s.label, facet1))
    # Same step, first facet probed — should move to another unprobed facet or None
    g2 = _nonfriction_gap(st)
    if g2 is not None and g2[0].label == s.label:
        assert g2[1][0] != facet1, "must not re-ask the same facet"
    # Probe all remaining facets for this step
    while True:
        g = _nonfriction_gap(st)
        if g is None or g[0].label != s.label:
            break
        st.probed_foci.add(st.focus_key(g[0].label, g[1][0]))
    # Fully probed unsatisfied step is no longer chased
    assert _nonfriction_gap(st) is None or _nonfriction_gap(st)[0].label != s.label
