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


def test_evidence_bar_keeps_recurring_drops_weak():
    assert passes_evidence_bar(_opp("a", "low", "recurring")) is True    # recurring always clears
    assert passes_evidence_bar(_opp("b", "high", "weak")) is False       # weak never clears
    assert passes_evidence_bar(_opp("c", "high", "one_off")) is True     # severe one-off clears
    assert passes_evidence_bar(_opp("d", "medium", "one_off")) is False  # minor one-off is an anecdote


def test_apply_evidence_bar_partitions_and_records_dropped():
    opps = [_opp("keep1", "low", "recurring"), _opp("keep2", "high", "one_off"),
            _opp("drop1", "medium", "one_off"), _opp("drop2", "high", "weak")]
    kept, dropped = apply_evidence_bar(opps)
    assert {o.step_label for o in kept} == {"keep1", "keep2"}
    assert {o.step_label for o in dropped} == {"drop1", "drop2"}
