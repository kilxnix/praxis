import pytest
from praxis.architect import Intervention
from praxis.business_case import score_interventions, prioritized, Assessment


def _ivs():
    return [Intervention("copy leads to spreadsheet", "auto-import leads", "the sheet",
                         "inbox access", "no manual typing")]


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
    async def complete_json(self, system, user, **kw):
        return self.payload


@pytest.mark.asyncio
async def test_score_anchors_and_normalizes():
    payload = {"assessments": [
        {"step_label": "copy leads to spreadsheet", "effort": "low", "time_saved": "high",
         "risk": "low", "disruption": "low", "priority": "quick win", "rationale": "obvious"},
        {"step_label": "ghost step", "effort": "low", "priority": "quick win"},   # unanchored -> dropped
        {"step_label": "copy leads to spreadsheet", "effort": "bogus",
         "priority": "nonsense"},   # bad values -> normalized
    ]}
    out = await score_interventions(FakeClient(payload), _ivs())
    assert len(out) == 2
    assert out[0].priority == "quick win" and out[0].time_saved == "high"
    assert out[1].effort == "medium"        # bad level normalized
    assert out[1].priority == "worth it"    # bad priority normalized


def test_prioritized_orders_quick_wins_first():
    a = [Assessment("x", "high", "low", "high", "high", "big bet", ""),
         Assessment("y", "low", "high", "low", "low", "quick win", ""),
         Assessment("z", "low", "low", "low", "low", "skip", "")]
    order = [x.priority for x in prioritized(a)]
    assert order == ["quick win", "big bet", "skip"]


@pytest.mark.asyncio
async def test_score_empty():
    assert await score_interventions(FakeClient({"assessments": []}), []) == []


def test_derive_priority_is_consistent_with_scores():
    from praxis.business_case import derive_priority
    assert derive_priority("high", "medium", "low") == "big bet"   # high effort is never a quick win
    assert derive_priority("low", "high", "low") == "quick win"
    assert derive_priority("medium", "low", "low") == "skip"       # costs effort, saves little
    assert derive_priority("high", "high", "low") == "big bet"
    assert derive_priority("medium", "medium", "medium") == "worth it"
