import pytest
from praxis.architect import Intervention
from praxis.business_case import Assessment
from praxis.skeptic import review, signed_off, Verdict


def _ivs():
    return [Intervention("copy leads", "auto-import", "sheet", "inbox", "no typing"),
            Intervention("send email", "auto-send", "gmail", "sheet", "auto")]


def _scores():
    return [Assessment("copy leads", "low", "high", "low", "low", "quick win", ""),
            Assessment("send email", "low", "medium", "high", "low", "skip", "")]


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
    async def complete_json(self, system, user, **kw):
        return self.payload


@pytest.mark.asyncio
async def test_review_anchors_and_normalizes():
    payload = {"verdicts": [
        {"step_label": "copy leads", "verdict": "solid", "objection": ""},
        {"step_label": "send email", "verdict": "reject", "objection": "auto-send is risky"},
        {"step_label": "ghost", "verdict": "solid"},               # unanchored -> dropped
        {"step_label": "copy leads", "verdict": "??", "objection": "x"},  # bad -> weak
    ]}
    out = await review(FakeClient(payload), _ivs(), _scores())
    assert len(out) == 3
    assert out[0].verdict == "solid"
    assert out[1].verdict == "reject" and "risky" in out[1].objection
    assert out[2].verdict == "weak"    # normalized


def test_signed_off():
    assert signed_off([Verdict("a", "solid", ""), Verdict("b", "reject", "x")]) is True
    assert signed_off([Verdict("a", "weak", "x"), Verdict("b", "reject", "y")]) is False


@pytest.mark.asyncio
async def test_review_empty():
    assert await review(FakeClient({"verdicts": []}), [], []) == []
