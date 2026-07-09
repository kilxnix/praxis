from praxis.models import WorkflowModel, NodeType, Evidence
from praxis.analyst import Opportunity
from praxis.grounding import measure_grounding, substantiation, has_frequency_language


def _model_with_step(label, quotes_and_turns):
    m = WorkflowModel()
    ev = [Evidence(q, t) for q, t in quotes_and_turns]
    m.add_node(NodeType.STEP, label, ev)
    return m


def _opp(step, evidence):
    return Opportunity(step, "cap", "desc", evidence)


def test_weak_when_evidence_not_in_owner_words():
    # The owner never said anything like this — the analyst invented the anchor.
    m = _model_with_step("type into QuickBooks", [("I type invoices at night", 3)])
    o = _opp("type into QuickBooks", "predictive churn analytics dashboard")
    assert measure_grounding(o, m) == "weak"


def test_recurring_from_frequency_language():
    m = _model_with_step("type into QuickBooks", [("I type every single invoice by hand at night", 3)])
    o = _opp("type into QuickBooks", "I type every single invoice by hand")
    assert measure_grounding(o, m) == "recurring"          # "every" — owner's own frequency word


def test_recurring_from_multiple_turns():
    m = _model_with_step("type into QuickBooks",
                         [("I type invoices into the system", 3), ("I re-type them later too", 7)])
    o = _opp("type into QuickBooks", "I type invoices into the system")
    assert measure_grounding(o, m) == "recurring"          # returned to it across two turns


def test_one_off_when_single_plain_mention():
    m = _model_with_step("greet the customer", [("once a client asked me to sign a form", 4)])
    o = _opp("greet the customer", "once a client asked me to sign a form")
    assert measure_grounding(o, m) == "one_off"            # substantiated, single, no frequency word


def test_substantiation_and_frequency_helpers():
    assert substantiation("type invoices", {"i", "type", "invoices", "nightly"}) == 1.0
    assert substantiation("blockchain synergy", {"i", "type", "invoices"}) == 0.0
    assert has_frequency_language(["I do this every night"]) is True
    assert has_frequency_language(["I did it once"]) is False


from praxis.grounding import measure_burden, burden_severity


def test_burden_high_for_volume_and_duration_words():
    m = _model_with_step("edit photos", [("I cull thousands of images and edit for hours", 3)])
    assert burden_severity(measure_burden("edit photos", m)) == "high"   # thousands + hours


def test_burden_low_for_passing_mention():
    m = _model_with_step("verify a date", [("I glance at the calendar", 2)])
    assert burden_severity(measure_burden("verify a date", m)) == "low"


def test_burden_ranks_core_over_admin():
    m = _model_with_step("edit photos", [("thousands of photos take all night", 3)])
    m.add_node.__self__  # (model already has the step)
    from praxis.models import NodeType, Evidence
    m.add_node(NodeType.STEP, "verify a date", [Evidence("I check the date once", 4)])
    assert measure_burden("edit photos", m) > measure_burden("verify a date", m)
