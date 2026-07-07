import pytest
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis.analyst import find_opportunities, serialize_map


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
