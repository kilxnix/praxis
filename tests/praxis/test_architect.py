import pytest
from praxis.models import WorkflowModel, NodeType, Evidence
from praxis.analyst import Opportunity
from praxis.architect import design_interventions


def _map():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "copy leads to spreadsheet",
               [Evidence("I copy each lead into the sheet by hand", 1)])
    return m


def _opps():
    return [Opportunity("copy leads to spreadsheet",
                        "automate manual data transfer between tools",
                        "auto-import leads", "I copy each lead into the sheet by hand")]


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
    async def complete_json(self, system, user, **kw):
        return self.payload


@pytest.mark.asyncio
async def test_design_interventions_keeps_anchored_drops_ungrounded():
    payload = {"interventions": [
        {"step_label": "copy leads to spreadsheet",
         "what_it_does": "read the inbox and write rows to the sheet",
         "where_it_plugs_in": "the master spreadsheet",
         "inputs_needed": "inbox access", "changes_for_people": "no more manual typing"},
        {"step_label": "not a real step", "what_it_does": "x"},          # unanchored -> dropped
        {"step_label": "copy leads to spreadsheet", "what_it_does": ""},  # empty -> dropped
    ]}
    ivs = await design_interventions(FakeClient(payload), _map(), _opps())
    assert len(ivs) == 1
    assert ivs[0].step_label == "copy leads to spreadsheet"
    assert "sheet" in ivs[0].what_it_does


@pytest.mark.asyncio
async def test_design_interventions_empty_opportunities():
    ivs = await design_interventions(FakeClient({"interventions": []}), _map(), [])
    assert ivs == []
