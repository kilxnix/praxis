import pytest
from praxis.principal import synthesize
from praxis.render import to_markdown


class _FC:
    def __init__(self, payload):
        self.payload = payload
    async def complete_json(self, system, user, **kw):
        return self.payload


@pytest.mark.asyncio
async def test_synthesize_adds_pains_summary_outcomes():
    deliverable = {"where_ai_fits": [
        {"step": "copy leads", "what_it_does": "Zapier IMAP integration to the sheet"}]}
    transcript = [{"role": "assistant", "content": "walk me through it"},
                  {"role": "user", "content": "I copy every lead by hand, it's a pain"}]
    payload = {"summary": "You lose time on manual copying.",
               "pains": ["copying every lead by hand", "jumping between tools"],
               "outcomes": [{"step": "copy leads", "outcome": "You stop copying leads by hand"}]}
    d = await synthesize(_FC(payload), transcript, deliverable)
    assert d["summary"].startswith("You lose")
    assert "copying every lead by hand" in d["pains"]
    assert d["where_ai_fits"][0]["outcome"] == "You stop copying leads by hand"


@pytest.mark.asyncio
async def test_synthesize_matches_outcomes_by_canonical_label():
    # The synthesizer rewords the step label; the outcome must still attach (else render falls
    # back to the raw technical sentence for the headline and to bare steps in the rollout).
    deliverable = {"where_ai_fits": [
        {"step": "copy leads", "what_it_does": "auto-import to the sheet"}]}
    transcript = [{"role": "user", "content": "I copy every lead by hand"}]
    payload = {"summary": "s", "pains": ["p"],
               "outcomes": [{"step": "Copying Leads", "outcome": "You stop copying leads by hand"}]}
    d = await synthesize(_FC(payload), transcript, deliverable)
    assert d["where_ai_fits"][0]["outcome"] == "You stop copying leads by hand"


@pytest.mark.asyncio
async def test_synthesize_positional_fallback_for_reworded_step():
    deliverable = {"where_ai_fits": [
        {"step": "copy leads", "what_it_does": "auto-import to the sheet"}]}
    transcript = [{"role": "user", "content": "I copy every lead by hand"}]
    payload = {"summary": "s", "pains": ["p"],
               "outcomes": [{"step": "the whole lead intake thing", "outcome": "You stop retyping leads"}]}
    d = await synthesize(_FC(payload), transcript, deliverable)
    assert d["where_ai_fits"][0]["outcome"] == "You stop retyping leads"


@pytest.mark.asyncio
async def test_synthesize_survives_empty_result():
    deliverable = {"where_ai_fits": []}
    d = await synthesize(_FC({}), [], deliverable)
    assert d == {"where_ai_fits": []}          # unchanged, no crash


def test_render_leads_with_summary_pains_and_outcomes():
    d = {"summary": "Here's the big picture.", "pains": ["copying leads by hand"],
         "workflow_mirror": ["copy leads"],
         "where_ai_fits": [{"step": "copy leads", "outcome": "You stop copying leads by hand",
                            "what_it_does": "technical detail here", "priority": "quick win",
                            "effort": "low", "time_saved": "high", "risk": "low"}],
         "rollout": ["copy leads"], "not_recommending": []}
    md = to_markdown(d)
    assert "Here's the big picture." in md                       # summary leads
    assert "copying leads by hand" in md                         # plain-language pain
    assert "You stop copying leads by hand" in md                # outcome is the headline
    assert "technical detail here" not in md                     # technical 'how' NOT leaked


def test_render_pains_fallback_to_friction_nodes():
    d = {"where_it_hurts": [{"step": "x", "friction": ["slow"]}], "where_ai_fits": [],
         "rollout": [], "not_recommending": [], "workflow_mirror": ["x"]}
    md = to_markdown(d)
    assert "slow" in md                                          # falls back when no synth pains
