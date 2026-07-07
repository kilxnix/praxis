"""Conducts the diagnostic firm over a shared EngagementState (the blackboard). Not a strict
linear pipe: the Principal conducts, every agent's output lands on the shared state (so any
agent can use any other's work), the Skeptic can bounce rejected/weak interventions BACK to
the Architect for a redesign, and every action + hand-off is recorded on the engagement log.

Hardening: the content-gating stages retry on an empty (stochastic) LLM return."""
from praxis.engagement import EngagementState
from praxis.analyst import find_opportunities
from praxis.architect import design_interventions, redesign_interventions
from praxis.business_case import score_interventions
from praxis.skeptic import review
from praxis.principal import assemble_deliverable


async def _attempt(fn, tries=3):
    result = []
    for _ in range(tries):
        result = await fn()
        if result:
            return result
    return result


def _tally(verdicts):
    return (sum(1 for v in verdicts if v.verdict == "solid"),
            sum(1 for v in verdicts if v.verdict == "weak"),
            sum(1 for v in verdicts if v.verdict == "reject"))


async def run_firm(client, model, max_redo=1):
    """Run the firm; returns the full EngagementState (map, every stage's output,
    the recorded log, and the deliverable)."""
    state = EngagementState(model_dict=model.to_dict())
    state.record("principal", "convened", "conducting the engagement over the workflow map")

    opportunities = await _attempt(lambda: find_opportunities(client, model))
    state.opportunities = opportunities
    state.record("analyst", "found_opportunities",
                 f"marked {len(opportunities)} AI-opportunity points",
                 consumed_from="discovery", count=len(opportunities))
    if not opportunities:
        state.deliverable = assemble_deliverable(model, [], [], [], [])
        state.record("principal", "assembled_deliverable", "no opportunities found")
        return state

    interventions = await _attempt(lambda: design_interventions(client, model, opportunities))
    state.interventions = interventions
    state.record("architect", "designed_interventions",
                 f"designed {len(interventions)} interventions",
                 consumed_from="analyst", count=len(interventions))

    assessments = await score_interventions(client, interventions)
    state.assessments = assessments
    state.record("business_case", "scored", f"scored {len(assessments)} interventions",
                 consumed_from="architect", count=len(assessments))

    verdicts = await review(client, interventions, assessments)
    state.verdicts = verdicts
    ns, nw, nr = _tally(verdicts)
    state.record("skeptic", "reviewed", f"{ns} solid, {nw} weak, {nr} reject",
                 consumed_from="architect+business_case", count=len(verdicts))

    # Non-linear: the Skeptic hands rejected/weak interventions BACK to the Architect.
    redo = 0
    while redo < max_redo:
        flagged = [v.step_label for v in verdicts if v.verdict in ("reject", "weak")]
        if not flagged:
            break
        objections = {v.step_label: v.objection for v in verdicts if v.step_label in flagged}
        state.record("skeptic", "bounced_to_architect",
                     f"sent {len(flagged)} back to redesign: {flagged}",
                     consumed_from="skeptic", count=len(flagged))
        flagged_opps = [o for o in opportunities if o.step_label in flagged]
        revised = await _attempt(
            lambda: redesign_interventions(client, model, flagged_opps, objections))
        rev_by = {iv.step_label: iv for iv in revised}
        interventions = [rev_by.get(iv.step_label, iv) for iv in interventions]
        state.interventions = interventions
        state.record("architect", "revised_interventions",
                     f"redesigned {len(revised)} to address the objections",
                     consumed_from="skeptic", count=len(revised))
        assessments = await score_interventions(client, interventions)
        state.assessments = assessments
        verdicts = await review(client, interventions, assessments)
        state.verdicts = verdicts
        ns, nw, nr = _tally(verdicts)
        state.record("skeptic", "re_reviewed",
                     f"after redesign: {ns} solid, {nw} weak, {nr} reject",
                     consumed_from="architect", count=len(verdicts))
        redo += 1

    deliverable = assemble_deliverable(model, opportunities, interventions,
                                       assessments, verdicts)
    state.deliverable = deliverable
    state.record("principal", "assembled_deliverable",
                 f"{len(deliverable['where_ai_fits'])} recommended, "
                 f"{len(deliverable['not_recommending'])} set aside",
                 consumed_from="all", count=len(deliverable["where_ai_fits"]))
    return state
