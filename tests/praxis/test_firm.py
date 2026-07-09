import pytest
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis.architect import Intervention
from praxis.business_case import Assessment
from praxis.skeptic import Verdict
from praxis.principal import assemble_deliverable
from praxis.firm import run_firm


def _ev():
    return [Evidence("q", 1)]


def test_assemble_sections_reject_removed_and_ordered():
    m = WorkflowModel()
    s1 = m.add_node(NodeType.STEP, "copy leads", _ev())
    m.add_node(NodeType.STEP, "send email", _ev())
    fr = m.add_node(NodeType.FRICTION, "slow", _ev())
    m.add_edge(EdgeType.CAUSES, s1.id, fr.id, _ev())
    ivs = [Intervention("copy leads", "auto-import", "sheet", "inbox", "no typing"),
           Intervention("send email", "auto-send", "gmail", "sheet", "auto")]
    scores = [Assessment("copy leads", "low", "high", "low", "low", "quick win", "x"),
              Assessment("send email", "low", "medium", "high", "low", "skip", "risky")]
    verdicts = [Verdict("copy leads", "solid", ""),
                Verdict("send email", "reject", "auto-send is risky")]
    d = assemble_deliverable(m, [], ivs, scores, verdicts)
    assert d["workflow_mirror"] == ["copy leads", "send email"]
    assert d["where_it_hurts"] == [{"step": "copy leads", "friction": ["slow"]}]
    assert [e["step"] for e in d["where_ai_fits"]] == ["copy leads"]   # rejected one removed
    assert d["not_recommending"][0]["step"] == "send email"
    assert d["rollout"] == ["copy leads"]


def test_weak_verdict_is_set_aside_not_recommended():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "x", _ev())
    ivs = [Intervention("x", "do", "w", "n", "c")]
    scores = [Assessment("x", "low", "high", "low", "low", "quick win", "")]
    verdicts = [Verdict("x", "weak", "watch the data")]
    d = assemble_deliverable(m, [], ivs, scores, verdicts)
    assert d["where_ai_fits"] == []                             # weak is NOT recommended
    assert d["not_recommending"][0]["reason"] == "watch the data"


class QueueClient:
    def __init__(self, responses):
        self.responses = list(responses)
    async def complete_json(self, system, user, **kw):
        return self.responses.pop(0) if self.responses else {}


@pytest.mark.asyncio
async def test_run_firm_produces_deliverable():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "copy leads", [Evidence("I copy every lead by hand all day, hundreds of them", 1)])
    responses = [
        {"opportunities": [{"step_label": "copy leads",
                            "capability": "automate manual data transfer between tools",
                            "description": "auto-import", "evidence": "I copy by hand"}]},
        {"interventions": [{"step_label": "copy leads", "what_it_does": "auto-import to sheet",
                            "where_it_plugs_in": "sheet", "inputs_needed": "inbox",
                            "changes_for_people": "no typing"}]},
        {"assessments": [{"step_label": "copy leads", "effort": "low", "time_saved": "high",
                          "risk": "low", "disruption": "low", "priority": "quick win",
                          "rationale": "obvious"}]},
        {"verdicts": [{"step_label": "copy leads", "verdict": "solid", "objection": ""}]},
    ]
    state = await run_firm(QueueClient(responses), m)
    d = state.deliverable
    assert d["workflow_mirror"] == ["copy leads"]
    assert [e["step"] for e in d["where_ai_fits"]] == ["copy leads"]
    assert d["rollout"] == ["copy leads"]
    actions = [e.action for e in state.log]                 # the engagement is recorded
    assert "found_opportunities" in actions and "assembled_deliverable" in actions


class RetryClient:
    """Empty on the first opportunities attempt, then real data — exercises _attempt retry."""
    def __init__(self):
        self.script = [
            {},  # first find_opportunities attempt: empty -> retry
            {"opportunities": [{"step_label": "copy leads",
                                "capability": "automate manual data transfer between tools",
                                "description": "auto-import", "evidence": "I copy by hand"}]},
            {"interventions": [{"step_label": "copy leads", "what_it_does": "auto-import",
                                "where_it_plugs_in": "sheet", "inputs_needed": "inbox",
                                "changes_for_people": "no typing"}]},
            {"assessments": [{"step_label": "copy leads", "effort": "low", "time_saved": "high",
                              "risk": "low", "disruption": "low", "priority": "quick win",
                              "rationale": "obvious"}]},
            {"verdicts": [{"step_label": "copy leads", "verdict": "solid", "objection": ""}]},
        ]
    async def complete_json(self, system, user, **kw):
        return self.script.pop(0) if self.script else {}


@pytest.mark.asyncio
async def test_run_firm_retries_empty_stage():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "copy leads", [Evidence("I copy every lead by hand all day, hundreds of them", 1)])
    state = await run_firm(RetryClient(), m)
    assert [e["step"] for e in state.deliverable["where_ai_fits"]] == ["copy leads"]  # recovered


class BounceClient:
    """Skeptic rejects the first design; after the bounce-back the redesign is solid."""
    def __init__(self):
        self.script = [
            {"opportunities": [{"step_label": "copy leads",
                                "capability": "automate manual data transfer between tools",
                                "description": "auto-import", "evidence": "by hand"}]},
            {"interventions": [{"step_label": "copy leads", "what_it_does": "v1 auto-send all",
                                "where_it_plugs_in": "sheet", "inputs_needed": "inbox",
                                "changes_for_people": "none"}]},
            {"assessments": [{"step_label": "copy leads", "effort": "low", "time_saved": "high",
                              "risk": "high", "disruption": "low", "priority": "quick win",
                              "rationale": "x"}]},
            {"verdicts": [{"step_label": "copy leads", "verdict": "reject",
                           "objection": "too risky as designed"}]},
            # --- bounce back to Architect ---
            {"interventions": [{"step_label": "copy leads",
                                "what_it_does": "v2 draft for human review",
                                "where_it_plugs_in": "sheet", "inputs_needed": "inbox",
                                "changes_for_people": "review first"}]},
            {"assessments": [{"step_label": "copy leads", "effort": "low", "time_saved": "high",
                              "risk": "low", "disruption": "low", "priority": "quick win",
                              "rationale": "safer"}]},
            {"verdicts": [{"step_label": "copy leads", "verdict": "solid", "objection": ""}]},
        ]
    async def complete_json(self, system, user, **kw):
        return self.script.pop(0) if self.script else {}


@pytest.mark.asyncio
async def test_run_firm_bounces_rejected_to_architect():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "copy leads", [Evidence("I copy every lead by hand all day, hundreds of them", 1)])
    state = await run_firm(BounceClient(), m, max_redo=1)
    actions = [e.action for e in state.log]
    assert "bounced_to_architect" in actions          # non-linear feedback happened
    assert "revised_interventions" in actions
    fits = state.deliverable["where_ai_fits"]
    assert [e["step"] for e in fits] == ["copy leads"]  # the redesign shipped
    assert "review" in fits[0]["what_it_does"]          # it's the v2, safer design


def test_assemble_ranks_by_severity_caps_and_filters_big_bets():
    from praxis.analyst import Opportunity
    m = WorkflowModel()
    for lbl in ("a", "b", "c", "d", "e", "f", "g"):
        m.add_node(NodeType.STEP, lbl, _ev())
    opps = [Opportunity(l, "cap", "d", "ev", sev) for l, sev in
            [("a", "high"), ("b", "high"), ("c", "medium"), ("d", "low"),
             ("e", "low"), ("f", "high"), ("g", "low")]]
    ivs = [Intervention(l, "do", "w", "n", "c") for l in ("a", "b", "c", "d", "e", "f", "g")]
    scores = [Assessment("a", "low", "high", "low", "low", "quick win", ""),
              Assessment("b", "low", "high", "low", "low", "quick win", ""),
              Assessment("c", "low", "high", "low", "low", "quick win", ""),
              Assessment("d", "low", "high", "low", "low", "quick win", ""),
              Assessment("e", "low", "high", "low", "low", "quick win", ""),   # 5th -> overflow
              Assessment("f", "high", "high", "low", "low", "big bet", ""),     # worthwhile big bet
              Assessment("g", "low", "low", "low", "low", "big bet", "")]        # low-value -> dropped
    verdicts = [Verdict(l, "solid", "") for l in ("a", "b", "c", "d", "e", "f", "g")]
    dv = assemble_deliverable(m, opps, ivs, scores, verdicts)
    steps = [x["step"] for x in dv["where_ai_fits"]]
    assert len(steps) == 4                              # stable cap, not 1 and not 7
    assert set(steps[:2]) == {"a", "b"}                 # highest-severity pains ranked first
    later = [x["step"] for x in dv["bigger_or_later"]]
    assert "f" in later                                 # worthwhile big bet -> later
    assert "g" not in later and "g" not in steps        # low-value big bet dropped (a real 'no')


class DeliberateClient:
    """Architect proposes a bare design; skeptic challenges; architect refines to a strong one.
    Route on the requested JSON shape (verdicts vs interventions), not on words that appear in
    multiple prompts."""
    def __init__(self):
        self.reviews = 0
    async def complete_json(self, system, user, **kw):
        if '"verdicts"' in system:                      # skeptic review
            self.reviews += 1
            if self.reviews == 1:
                return {"verdicts": [{"step_label": "edit thousands of photos",
                                      "verdict": "weak", "objection": "does not actually cull for her"}]}
            return {"verdicts": [{"step_label": "edit thousands of photos", "verdict": "solid", "objection": ""}]}
        if "redesign" in system.lower():                # architect redesign after the challenge
            return {"interventions": [{"step_label": "edit thousands of photos",
                    "what_it_does": "auto-culls and pre-edits the batch, she reviews the keepers"}]}
        return {"interventions": [{"step_label": "edit thousands of photos",
                "what_it_does": "opens the editor for her"}]}   # bare first proposal


@pytest.mark.asyncio
async def test_deliberate_hard_refines_high_burden_step():
    from praxis.firm import _deliberate_hard
    from praxis.analyst import Opportunity
    from praxis.engagement import EngagementState
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "edit thousands of photos",
               [Evidence("I cull thousands of images and edit for hours every wedding", 1)])
    opps = [Opportunity("edit thousands of photos", "vision", "auto-edit", "thousands of images")]
    state = EngagementState(model_dict=m.to_dict())
    strong = await _deliberate_hard(DeliberateClient(), m, opps, firm=None, state=state)
    assert "edit thousands of photos" in strong                    # the hard step was deliberated
    assert "auto-culls" in strong["edit thousands of photos"].what_it_does   # refined, not timid
    assert any(e.action == "deliberated_with_skeptic" for e in state.log)    # collaboration recorded


@pytest.mark.asyncio
async def test_deliberate_hard_skips_low_burden_steps():
    from praxis.firm import _deliberate_hard
    from praxis.analyst import Opportunity
    from praxis.engagement import EngagementState
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "verify a date", [Evidence("I glance at the calendar once", 1)])
    opps = [Opportunity("verify a date", "check", "verify", "glance")]
    state = EngagementState(model_dict=m.to_dict())
    strong = await _deliberate_hard(DeliberateClient(), m, opps, firm=None, state=state)
    assert strong == {}                                            # low burden -> no deliberation
