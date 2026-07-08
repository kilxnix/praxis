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
async def test_design_interventions_coerces_list_valued_fields():
    # The model sometimes returns list values where we expect prose; join, don't crash.
    payload = {"interventions": [
        {"step_label": "copy leads to spreadsheet",
         "what_it_does": "read the inbox and write rows",
         "where_it_plugs_in": "the sheet",
         "inputs_needed": ["inbox access", "the spreadsheet"],   # list, not string
         "changes_for_people": "no more typing"},
    ]}
    ivs = await design_interventions(FakeClient(payload), _map(), _opps())
    assert len(ivs) == 1
    assert ivs[0].inputs_needed == "inbox access; the spreadsheet"


@pytest.mark.asyncio
async def test_design_interventions_empty_opportunities():
    ivs = await design_interventions(FakeClient({"interventions": []}), _map(), [])
    assert ivs == []


def _two_opps():
    return [
        Opportunity("copy leads to spreadsheet", "automate manual data transfer",
                    "auto-import leads", "I copy each lead into the sheet by hand"),
        Opportunity("send follow-up email", "draft or generate text",
                    "draft the reply", "then I type out a follow-up to each one"),
    ]


class DropsThenCoversClient:
    """First call designs only the first opportunity (drops the second); the re-prompt for the
    missing one then covers it. Proves the Architect can't silently drop an opportunity."""
    def __init__(self):
        self.calls = 0
    async def complete_json(self, system, user, **kw):
        self.calls += 1
        if self.calls == 1:
            return {"interventions": [
                {"step_label": "copy leads to spreadsheet", "what_it_does": "auto-import rows"}]}
        return {"interventions": [
            {"step_label": "send follow-up email", "what_it_does": "draft each reply for review"}]}


@pytest.mark.asyncio
async def test_design_interventions_reprompts_for_dropped_opportunity():
    from praxis.models import NodeType, Evidence
    m = _map()
    m.add_node(NodeType.STEP, "send follow-up email", [Evidence("I type out a follow-up", 1)])
    client = DropsThenCoversClient()
    ivs = await design_interventions(client, m, _two_opps())
    labels = {iv.step_label for iv in ivs}
    assert labels == {"copy leads to spreadsheet", "send follow-up email"}   # both covered
    assert client.calls == 2                                                 # took a re-prompt


@pytest.mark.asyncio
async def test_design_interventions_dedups_by_step():
    payload = {"interventions": [
        {"step_label": "copy leads to spreadsheet", "what_it_does": "first idea"},
        {"step_label": "copy leads to spreadsheet", "what_it_does": "second idea"},
    ]}
    ivs = await design_interventions(FakeClient(payload), _map(), _opps())
    assert len(ivs) == 1                       # one intervention per step
    assert ivs[0].what_it_does == "first idea"


from praxis.architect import is_timid, Intervention as _IV


def test_is_timid_flags_non_solutions():
    assert is_timid(_IV("s", "Remains completely inert during the call", "x", "y", "z")) is True
    assert is_timid(_IV("s", "provides an empty document", "x", "y", "z")) is True
    assert is_timid(_IV("s", "captures it so you still type it later", "x", "y", "z")) is True
    assert is_timid(_IV("s", "reads the ticket and writes every line into QuickBooks for you",
                        "x", "y", "you review and approve")) is False


class BoldensClient:
    """First design is timid; the bolden pass returns a real one."""
    def __init__(self):
        self.calls = 0
    async def complete_json(self, system, user, **kw):
        self.calls += 1
        if "TOO TIMID" in user or "too timid" in system.lower():
            return {"interventions": [{"step_label": "type into QuickBooks",
                    "what_it_does": "reads the paper ticket and enters every line into QuickBooks for you"}]}
        return {"interventions": [{"step_label": "type into QuickBooks",
                "what_it_does": "provides an empty document; you still type each line"}]}


@pytest.mark.asyncio
async def test_design_interventions_boldens_timid_design():
    from praxis.models import WorkflowModel, NodeType, Evidence
    from praxis.analyst import Opportunity
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "type into QuickBooks", [Evidence("I type it all in at night", 1)])
    opps = [Opportunity("type into QuickBooks", "automate data entry", "d", "I type it all in")]
    ivs = await design_interventions(BoldensClient(), m, opps)
    assert len(ivs) == 1
    assert not is_timid(ivs[0])                       # the timid design was replaced
    assert "for you" in ivs[0].what_it_does
