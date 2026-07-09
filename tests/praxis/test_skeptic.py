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


from praxis.skeptic import ground_verdicts, _is_preference_objection
from praxis.models import WorkflowModel, NodeType, Evidence


def test_preference_vs_risk_objection_detection():
    assert _is_preference_objection("the owner values keeping a human in the loop") is True
    assert _is_preference_objection("removes their final authority before invoicing") is True
    # a concrete risk is NOT a preference objection, even if it mentions control
    assert _is_preference_objection("the OCR could misread and bill the wrong amount") is False
    assert _is_preference_objection("it could fail silently on bad data") is False


def test_ground_verdicts_flips_invented_preference_reject_on_high_burden_step():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "type into QuickBooks",
               [Evidence("I type every work order into QuickBooks all day, hundreds of them", 1)])
    # skeptic rejected the shop's biggest drudgery citing an invented preference
    vs = [Verdict("type into QuickBooks", "reject", "the owner values keeping final authority")]
    out = ground_verdicts(vs, m)
    assert out[0].verdict == "solid"        # high burden + preference-only objection -> overturned


def test_ground_verdicts_keeps_concrete_risk_rejection():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "type into QuickBooks",
               [Evidence("I type every work order into QuickBooks all day, hundreds of them", 1)])
    vs = [Verdict("type into QuickBooks", "reject", "the OCR could misread and bill the wrong client")]
    out = ground_verdicts(vs, m)
    assert out[0].verdict == "reject"       # a real risk still stands


def test_ground_verdicts_leaves_low_burden_untouched():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "glance at calendar", [Evidence("I glance once", 1)])
    vs = [Verdict("glance at calendar", "reject", "the owner values doing this themselves")]
    out = ground_verdicts(vs, m)
    assert out[0].verdict == "reject"       # low burden -> not overridden
