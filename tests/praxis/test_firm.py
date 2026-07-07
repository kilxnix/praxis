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


def test_weak_verdict_carries_caveat_forward():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "x", _ev())
    ivs = [Intervention("x", "do", "w", "n", "c")]
    scores = [Assessment("x", "low", "high", "low", "low", "quick win", "")]
    verdicts = [Verdict("x", "weak", "watch the data")]
    d = assemble_deliverable(m, [], ivs, scores, verdicts)
    assert d["where_ai_fits"][0]["caveat"] == "watch the data"


class QueueClient:
    def __init__(self, responses):
        self.responses = list(responses)
    async def complete_json(self, system, user, **kw):
        return self.responses.pop(0) if self.responses else {}


@pytest.mark.asyncio
async def test_run_firm_produces_deliverable():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "copy leads", [Evidence("I copy by hand", 1)])
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
    d = await run_firm(QueueClient(responses), m)
    assert d["workflow_mirror"] == ["copy leads"]
    assert [e["step"] for e in d["where_ai_fits"]] == ["copy leads"]
    assert d["rollout"] == ["copy leads"]


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
    m.add_node(NodeType.STEP, "copy leads", [Evidence("I copy by hand", 1)])
    d = await run_firm(RetryClient(), m)
    assert [e["step"] for e in d["where_ai_fits"]] == ["copy leads"]   # recovered after retry
