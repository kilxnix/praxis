"""Runs the diagnostic firm over a Discovery workflow map:
Analyst -> Architect -> Business-case -> Skeptic -> Principal, producing the deliverable.

Hardening: the LLM stages occasionally return empty (stochastic parse/empty). A stage that
returns nothing would silently empty the deliverable, so the two content-gating stages
(opportunities, interventions) retry until non-empty or the attempt cap is hit."""
from praxis.analyst import find_opportunities
from praxis.architect import design_interventions
from praxis.business_case import score_interventions
from praxis.skeptic import review
from praxis.principal import assemble_deliverable


async def _attempt(fn, tries=3):
    """Call an async producer, retrying while it returns an empty result."""
    result = []
    for _ in range(tries):
        result = await fn()
        if result:
            return result
    return result


async def run_firm(client, model):
    opportunities = await _attempt(lambda: find_opportunities(client, model))
    if not opportunities:
        return assemble_deliverable(model, [], [], [], [])
    interventions = await _attempt(lambda: design_interventions(client, model, opportunities))
    assessments = await score_interventions(client, interventions)
    verdicts = await review(client, interventions, assessments)
    return assemble_deliverable(model, opportunities, interventions, assessments, verdicts)
