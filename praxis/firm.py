"""Runs the diagnostic firm over a Discovery workflow map:
Analyst -> Architect -> Business-case -> Skeptic -> Principal, producing the deliverable."""
from praxis.analyst import find_opportunities
from praxis.architect import design_interventions
from praxis.business_case import score_interventions
from praxis.skeptic import review
from praxis.principal import assemble_deliverable


async def run_firm(client, model):
    opportunities = await find_opportunities(client, model)
    interventions = await design_interventions(client, model, opportunities)
    assessments = await score_interventions(client, interventions)
    verdicts = await review(client, interventions, assessments)
    return assemble_deliverable(model, opportunities, interventions, assessments, verdicts)
