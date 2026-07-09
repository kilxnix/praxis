"""Conducts the diagnostic firm over a shared EngagementState (the blackboard). Not a strict
linear pipe: the Principal conducts, every agent's output lands on the shared state (so any
agent can use any other's work), the Skeptic can bounce rejected/weak interventions BACK to
the Architect for a redesign, and every action + hand-off is recorded on the engagement log.

Hardening: the content-gating stages retry on an empty (stochastic) LLM return."""
from praxis.engagement import EngagementState
from praxis.analyst import find_opportunities, apply_evidence_bar
from praxis.architect import design_interventions, redesign_interventions
from praxis.business_case import score_interventions
from praxis.skeptic import review
from praxis.principal import assemble_deliverable
from praxis.analyst import serialize_map
from praxis.firm_agent import study_firm, morph_firm
from praxis.models import WorkflowModel


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


def _mem(firm, key):
    """The compact understanding that agent brings to a decision — their learned lessons plus a
    capped read of THIS business — or '' if the firm didn't sit in on the interview."""
    agent = firm.get(key) if firm else None
    if not agent:
        return ""
    text = agent.understanding()
    return text if text.strip() else ""


async def run_firm(client, model, max_redo=1, firm=None, business_label="", transcript=None):
    """Run the firm; returns the full EngagementState (map, every stage's output, the recorded
    log, and the deliverable). If `firm` is passed, the members first STUDY the whole interview
    (one pass each, at convene — not per turn), then MORPH to this business, then decide from
    that understanding. The interview no longer costs 5 agent-calls every turn."""
    state = EngagementState(model_dict=model.to_dict())
    state.record("principal", "convened", "conducting the engagement over the workflow map")

    if firm:
        if transcript:
            await study_firm(firm, transcript, serialize_map(model))
            state.record("principal", "firm_studied",
                         "each member read the full interview and formed their own understanding",
                         consumed_from="discovery")
        await morph_firm(firm, business_label)
        state.record("principal", "firm_morphed",
                     "each member synthesized this business into a stance to reason from",
                     consumed_from="discovery")

    found = await _attempt(lambda: find_opportunities(client, model, _mem(firm, "analyst")))
    # Evidence bar: keep only opportunities grounded in real, recurring pain (or a severe
    # one-off); drop capability-driven guesses BEFORE design, so weak ideas never become
    # recommendations. Recorded transparently — never a silent truncation.
    opportunities, dropped = apply_evidence_bar(found)
    state.opportunities = opportunities
    state.record("analyst", "found_opportunities",
                 f"marked {len(found)} points; {len(opportunities)} cleared the evidence bar, "
                 f"{len(dropped)} dropped as one-off/weak",
                 consumed_from="discovery", count=len(opportunities))
    if dropped:
        state.record("analyst", "gated_weak_opportunities",
                     "set aside as not grounded in recurring pain: "
                     + "; ".join(f"{o.step_label} ({o.grounding})" for o in dropped),
                     consumed_from="analyst", count=len(dropped))
    if not opportunities:
        state.deliverable = assemble_deliverable(model, [], [], [], [])
        state.record("principal", "assembled_deliverable", "no opportunities found")
        return state

    interventions = await _attempt(
        lambda: design_interventions(client, model, opportunities, _mem(firm, "architect")))
    state.interventions = interventions
    state.record("architect", "designed_interventions",
                 f"designed {len(interventions)} interventions",
                 consumed_from="analyst", count=len(interventions))

    assessments = await _attempt(
        lambda: score_interventions(client, interventions, _mem(firm, "business_case")))
    state.assessments = assessments
    state.record("business_case", "scored", f"scored {len(assessments)} interventions",
                 consumed_from="architect", count=len(assessments))

    verdicts = await _attempt(
        lambda: review(client, interventions, assessments, _mem(firm, "skeptic")))
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
            lambda: redesign_interventions(client, model, flagged_opps, objections,
                                           _mem(firm, "architect")))
        rev_by = {iv.step_label: iv for iv in revised}
        interventions = [rev_by.get(iv.step_label, iv) for iv in interventions]
        state.interventions = interventions
        state.record("architect", "revised_interventions",
                     f"redesigned {len(revised)} to address the objections",
                     consumed_from="skeptic", count=len(revised))
        assessments = await _attempt(
            lambda: score_interventions(client, interventions, _mem(firm, "business_case")))
        state.assessments = assessments
        verdicts = await _attempt(
            lambda: review(client, interventions, assessments, _mem(firm, "skeptic")))
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
