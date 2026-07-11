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


def test_is_timid_flags_passive_safety_net_culling():
    """Videographer failure: design DISCLAIMS doing the volume work — must be replaced."""
    iv = _IV(
        "select usable clips",
        "Acts as a passive 'safety net' that only runs if the owner explicitly asks for help "
        "after their manual night shift. It does not replace or automate the culling process; "
        "instead, it takes the raw footage they already manually selected and simply organizes "
        "those specific files into folders.",
        "Premiere", "footage", "still does the cull by hand",
    )
    assert is_timid(iv) is True
    assert is_timid(_IV(
        "select usable clips",
        "AI scores every clip, auto-rejects throwaways, and hands a ranked shortlist she approves",
        "Premiere", "raw footage", "she only reviews the shortlist",
    )) is False


def test_is_timid_flags_dormant_creative_designs():
    """Designer failure: 'Remains dormant' / performs no drafting — must be replaced."""
    assert is_timid(_IV(
        "make changes in Illustrator",
        "Remains dormant. It does not scan PDFs, check brand guidelines against AI rulesets, "
        "or flag errors.",
        "Illustrator", "feedback", "nothing changes",
    )) is True
    assert is_timid(_IV(
        "send clarifying questions and quote",
        "Waits for a manual 'Ready' signal. Once signaled, it retrieves the raw email text "
        "but does NOT draft or send anything.",
        "email", "raw email", "owner still writes",
    )) is True


def test_owned_core_design_create_kind_for_sketch_and_illustrator():
    from praxis.architect import owned_core_design, is_timid, _core_kind
    from praxis.analyst import Opportunity
    sketch = Opportunity(
        "sketch concepts on paper",
        "generate first-draft creative or professional work (a proposal, an edit, a design "
        "variation, a diagnosis shortlist) for the expert to refine and approve",
        "Generate multiple rough concept variations",
        "I sketch concepts on paper for hours", "high")
    assert _core_kind(sketch) == "create"
    iv = owned_core_design(sketch)
    assert iv.is_buildable() and not is_timid(iv)
    assert "concept" in iv.what_it_does.lower() or "first-pass" in iv.what_it_does.lower()
    assert "blank page" in iv.what_it_does.lower() or "final creative" in iv.what_it_does.lower()
    # Success criterion is checkable (options exist), not aesthetic quality
    assert "3" in iv.success_criteria or "concept" in iv.success_criteria.lower()

    edit = Opportunity(
        "make changes in Illustrator",
        "generate first-draft creative",
        "apply client markup as first pass",
        "I make changes in Illustrator from the marked-up PDF", "high")
    assert _core_kind(edit) == "create"
    iv2 = owned_core_design(edit)
    assert iv2.is_buildable() and not is_timid(iv2)


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


@pytest.mark.asyncio
async def test_design_batches_and_does_not_return_empty_on_many_opportunities():
    # Many opportunities, each answered in a batch — must not truncate to zero.
    from praxis.models import WorkflowModel, NodeType, Evidence
    from praxis.analyst import Opportunity
    m = WorkflowModel()
    labels = [f"step {i}" for i in range(7)]
    for l in labels:
        m.add_node(NodeType.STEP, l, [Evidence(f"I do {l} a lot", 1)])
    opps = [Opportunity(l, "cap", "desc", f"I do {l} a lot") for l in labels]

    class BatchClient:
        """Answers whatever batch it's asked, one intervention per opp in the prompt."""
        async def complete_json(self, system, user, **kw):
            asked = [l for l in labels if f"step '{l}'" in user]
            return {"interventions": [
                {"step_label": l, "what_it_does": f"auto-does {l} for you",
                 "trigger": "t", "input_source": "i", "output_dest": "o",
                 "success_criteria": "c"} for l in asked]}
    ivs = await design_interventions(BatchClient(), m, opps)
    assert len(ivs) == 7                         # every opportunity covered across batches
    assert all(iv.is_buildable() for iv in ivs)


def test_fallback_interventions_never_empty_when_opportunities_exist():
    from praxis.architect import fallback_interventions, is_timid
    from praxis.analyst import Opportunity
    opps = [Opportunity("cull images", "cap", "sort thousands of photos", "I cull thousands")]
    ivs = fallback_interventions(opps)
    assert len(ivs) == 1 and ivs[0].step_label == "cull images"
    assert "cull images" in ivs[0].what_it_does
    assert ivs[0].is_buildable() is True          # fallbacks are now shippable, not prose-only
    assert is_timid(ivs[0]) is False


def test_owned_core_design_culling_is_buildable_and_active():
    from praxis.architect import owned_core_design, is_timid
    from praxis.analyst import Opportunity
    from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
    m = WorkflowModel()
    step = m.add_node(NodeType.STEP, "cull images in Lightroom",
                      [Evidence("I cull thousands of images for hours", 1)])
    tool = m.add_node(NodeType.TOOL, "Lightroom", [Evidence("in Lightroom", 1)])
    m.add_edge(EdgeType.USES, step.id, tool.id, [Evidence("in Lightroom", 1)])
    opp = Opportunity("cull images in Lightroom",
                      "do the heavy first pass on high-volume skilled work — pre-sort/pre-select (cull)",
                      "AI pre-sorts the gallery", "I cull thousands of images for hours", "high")
    iv = owned_core_design(opp, m)
    assert iv.is_buildable()
    assert not is_timid(iv)
    assert "Lightroom" in iv.where_it_plugs_in or "Lightroom" in iv.what_it_does
    assert iv.trigger and iv.success_criteria
    assert "shortlist" in iv.what_it_does.lower() or "scores" in iv.what_it_does.lower()


def test_ensure_shippable_replaces_timid_high_burden():
    from praxis.architect import Intervention, ensure_shippable_designs, is_timid
    from praxis.analyst import Opportunity
    from praxis.models import WorkflowModel, NodeType, Evidence
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "cull thousands of images",
               [Evidence("I cull thousands of images for hours after every wedding", 3)])
    opps = [Opportunity("cull thousands of images", "cull photos",
                        "sort the gallery", "I cull thousands", "high")]
    timid = [Intervention("cull thousands of images",
                          "acts as a silent observer that does not delete", "x", "y", "z")]
    out = ensure_shippable_designs(timid, opps, m)
    assert len(out) == 1
    assert not is_timid(out[0])
    assert out[0].is_buildable()
    assert out[0].step_label == "cull thousands of images"


def test_ensure_shippable_replaces_videographer_passive_safety_net():
    """Exact failure from event_videographer run: passive safety net disclaiming culling."""
    from praxis.architect import Intervention, ensure_shippable_designs, is_timid
    from praxis.analyst import Opportunity
    from praxis.models import WorkflowModel, NodeType, Evidence
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "select usable clips",
               [Evidence("I spend entire nights scrubbing through thousands of minutes", 3)])
    opps = [Opportunity(
        "select usable clips",
        "do the heavy first pass on high-volume skilled work — pre-sort/pre-select (cull)",
        "AI pre-sorts clips", "entire nights scrubbing through thousands of minutes", "high")]
    timid = [Intervention(
        "select usable clips",
        "Acts as a passive 'safety net' that only runs if the owner explicitly asks for help "
        "after their manual night shift. It does not replace or automate the culling process; "
        "instead, it takes the raw footage they already manually selected and simply organizes "
        "those specific files into folders based on event type.",
        "Premiere", "raw footage", "owner still culls manually",
        trigger="after cull", input_source="footage", output_dest="folders",
        success_criteria="files organized")]
    out = ensure_shippable_designs(timid, opps, m)
    assert not is_timid(out[0])
    assert out[0].is_buildable()
    assert "shortlist" in out[0].what_it_does.lower() or "scores" in out[0].what_it_does.lower()
    assert "does not replace" not in out[0].what_it_does.lower()


@pytest.mark.asyncio
async def test_design_interventions_replaces_timid_high_core_when_bolden_fails():
    """If the model keeps returning timid designs for high-severity culling, ensure_shippable
    still produces a buildable first-pass recommendation."""
    from praxis.models import WorkflowModel, NodeType, Evidence
    from praxis.analyst import Opportunity
    from praxis.architect import is_timid

    m = WorkflowModel()
    m.add_node(NodeType.STEP, "cull images",
               [Evidence("I cull thousands of images every wedding", 1)])
    opps = [Opportunity("cull images", "pre-sort cull", "sort photos",
                        "I cull thousands of images", "high")]

    class AlwaysTimid:
        async def complete_json(self, system, user, **kw):
            return {"interventions": [{
                "step_label": "cull images",
                "what_it_does": "acts as a silent observer that does not delete",
                "where_it_plugs_in": "x", "inputs_needed": "y", "changes_for_people": "z",
            }]}

    ivs = await design_interventions(AlwaysTimid(), m, opps)
    assert len(ivs) == 1
    assert not is_timid(ivs[0])
    assert ivs[0].is_buildable()
