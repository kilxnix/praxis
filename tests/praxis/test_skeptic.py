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
async def test_review_matches_by_canonical_label_and_normalizes():
    # Labels differ by case/punctuation; verdicts still map to the real interventions, one each.
    payload = {"verdicts": [
        {"step_label": "Copy Leads", "verdict": "solid", "objection": ""},
        {"step_label": "send email.", "verdict": "REJECT", "objection": "auto-send is risky"},
    ]}
    out = await review(FakeClient(payload), _ivs(), _scores())
    assert len(out) == 2
    by = {v.step_label: v for v in out}
    assert by["copy leads"].verdict == "solid"          # mapped back to the intervention's label
    assert by["send email"].verdict == "reject" and "risky" in by["send email"].objection


@pytest.mark.asyncio
async def test_review_positional_fallback_rescues_reworded_labels():
    # The model rewords every label so none string-match; it returns one verdict per
    # intervention in order, so the positional fallback still lands them (the bug that let the
    # whole quality gate return 0 verdicts).
    payload = {"verdicts": [
        {"step_label": "auto-import the leads", "verdict": "solid", "objection": ""},
        {"step_label": "sending the email out", "verdict": "weak", "objection": "risky"},
    ]}
    out = await review(FakeClient(payload), _ivs(), _scores())
    assert len(out) == 2
    by = {v.step_label: v for v in out}
    assert by["copy leads"].verdict == "solid"
    assert by["send email"].verdict == "weak" and "risky" in by["send email"].objection


@pytest.mark.asyncio
async def test_review_normalizes_unknown_verdict_to_weak():
    payload = {"verdicts": [{"step_label": "copy leads", "verdict": "??", "objection": "x"}]}
    out = await review(FakeClient(payload), _ivs(), _scores())
    assert len(out) == 1
    assert out[0].step_label == "copy leads" and out[0].verdict == "weak"


def test_signed_off():
    assert signed_off([Verdict("a", "solid", ""), Verdict("b", "reject", "x")]) is True
    assert signed_off([Verdict("a", "weak", "x"), Verdict("b", "reject", "y")]) is False


@pytest.mark.asyncio
async def test_review_empty():
    assert await review(FakeClient({"verdicts": []}), [], []) == []
