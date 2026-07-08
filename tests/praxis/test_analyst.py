import pytest
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis.analyst import (find_opportunities, serialize_map, Opportunity,
                            passes_evidence_bar, apply_evidence_bar)


def _map():
    m = WorkflowModel()
    s = m.add_node(NodeType.STEP, "copy leads to spreadsheet",
                   [Evidence("I copy each lead into the sheet by hand", 1)])
    a = m.add_node(NodeType.ACTOR, "me", [Evidence("I", 1)])
    t = m.add_node(NodeType.TOOL, "spreadsheet", [Evidence("the sheet", 1)])
    m.add_edge(EdgeType.PERFORMS, a.id, s.id, [Evidence("I", 1)])
    m.add_edge(EdgeType.USES, s.id, t.id, [Evidence("the sheet", 1)])
    return m


def test_serialize_map_includes_step_facets_and_evidence():
    out = serialize_map(_map())
    assert "copy leads to spreadsheet" in out
    assert "who=me" in out
    assert "tool=spreadsheet" in out
    assert "by hand" in out            # the client's own words are included


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
    async def complete_json(self, system, user, **kw):
        return self.payload


@pytest.mark.asyncio
async def test_find_opportunities_keeps_anchored_drops_ungrounded():
    payload = {"opportunities": [
        {"step_label": "copy leads to spreadsheet",
         "capability": "automate manual data transfer between tools",
         "description": "auto-import leads into the sheet",
         "evidence": "I copy each lead into the sheet by hand"},
        {"step_label": "not a real step", "capability": "x",
         "description": "y", "evidence": "z"},               # unanchored -> dropped
        {"step_label": "copy leads to spreadsheet", "capability": "x",
         "description": "d", "evidence": ""},                # no evidence -> dropped
    ]}
    opps = await find_opportunities(FakeClient(payload), _map())
    assert len(opps) == 1
    assert opps[0].step_label == "copy leads to spreadsheet"
    assert opps[0].capability.startswith("automate")


@pytest.mark.asyncio
async def test_find_opportunities_empty_map():
    opps = await find_opportunities(FakeClient({"opportunities": []}), WorkflowModel())
    assert opps == []


@pytest.mark.asyncio
async def test_find_opportunities_captures_grounding():
    payload = {"opportunities": [
        {"step_label": "copy leads to spreadsheet", "capability": "automate",
         "description": "d", "evidence": "I copy each lead by hand",
         "severity": "high", "grounding": "one_off"}]}
    opps = await find_opportunities(FakeClient(payload), _map())
    assert opps[0].grounding == "one_off"
    assert opps[0].severity == "high"


def _opp(label, severity, grounding):
    return Opportunity(label, "cap", "desc", "quote", severity, grounding)


def test_evidence_bar_drops_weak_and_trivial_oneoffs():
    assert passes_evidence_bar(_opp("a", "low", "recurring")) is True    # recurring always clears
    assert passes_evidence_bar(_opp("b", "high", "weak")) is False       # invented anchor: dropped
    assert passes_evidence_bar(_opp("b2", "low", "weak")) is False       # weak dropped regardless
    assert passes_evidence_bar(_opp("c", "high", "one_off")) is True     # notable one-off clears
    assert passes_evidence_bar(_opp("c2", "medium", "one_off")) is True  # medium one-off clears
    assert passes_evidence_bar(_opp("d", "low", "one_off")) is False     # trivial anecdote dropped


def test_apply_evidence_bar_partitions_and_records_dropped():
    opps = [_opp("keep1", "low", "recurring"), _opp("keep2", "high", "one_off"),
            _opp("drop1", "low", "one_off"), _opp("drop2", "high", "weak")]
    kept, dropped = apply_evidence_bar(opps)
    assert {o.step_label for o in kept} == {"keep1", "keep2"}
    assert {o.step_label for o in dropped} == {"drop1", "drop2"}


def _three_step_map():
    m = WorkflowModel()
    for lbl, q in [("type into QuickBooks", "I type it all in at night"),
                   ("re-key part costs", "then I re-enter the part costs"),
                   ("greet the customer", "I say hi when they arrive")]:
        m.add_node(NodeType.STEP, lbl, [Evidence(q, 1)])
    return m


class LazyThenCoversClient:
    """First pass flags only 1 of 3 steps (the lazy Analyst); the coverage re-prompt then
    covers the ignored ones — one real opportunity, one explicit no_fit."""
    def __init__(self):
        self.calls = 0
    async def complete_json(self, system, user, **kw):
        self.calls += 1
        if self.calls == 1:
            return {"opportunities": [
                {"step_label": "type into QuickBooks", "capability": "automate data entry",
                 "description": "auto-enter", "evidence": "I type it all in at night",
                 "severity": "high", "grounding": "recurring"}]}
        return {"opportunities": [
            {"step_label": "re-key part costs", "capability": "automate data entry",
             "description": "auto-enter costs", "evidence": "then I re-enter the part costs",
             "severity": "high", "grounding": "recurring"},
            {"step_label": "greet the customer", "no_fit": True}]}


@pytest.mark.asyncio
async def test_find_opportunities_forces_coverage_of_ignored_steps():
    client = LazyThenCoversClient()
    opps = await find_opportunities(client, _three_step_map())
    labels = {o.step_label for o in opps}
    assert labels == {"type into QuickBooks", "re-key part costs"}   # both data-entry steps caught
    assert "greet the customer" not in labels                        # legit no_fit, not forced
    assert client.calls == 2                                          # took a coverage re-prompt


class DuplicateOppsClient:
    def __init__(self, payload):
        self.payload = payload
    async def complete_json(self, system, user, **kw):
        return self.payload


@pytest.mark.asyncio
async def test_find_opportunities_dedups_same_step():
    payload = {"opportunities": [
        {"step_label": "type into QuickBooks", "capability": "c", "description": "first",
         "evidence": "I type it all in at night", "severity": "high", "grounding": "recurring"},
        {"step_label": "type into QuickBooks", "capability": "c", "description": "second",
         "evidence": "I type it all in at night", "severity": "high", "grounding": "recurring"}]}
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "type into QuickBooks", [Evidence("I type it all in at night", 1)])
    opps = await find_opportunities(DuplicateOppsClient(payload), m)
    assert len(opps) == 1                        # same step can't be flagged twice
    assert opps[0].description == "first"
