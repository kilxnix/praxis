"""Conducts the diagnostic firm over a shared EngagementState (the blackboard). Not a strict
linear pipe: the Principal conducts, every agent's output lands on the shared state (so any
agent can use any other's work), the Skeptic can bounce rejected/weak interventions BACK to
the Architect for a redesign, and every action + hand-off is recorded on the engagement log.

Hardening: the content-gating stages retry on an empty (stochastic) LLM return."""
from praxis.engagement import EngagementState
from praxis.analyst import find_opportunities, apply_evidence_bar, fallback_opportunities
from praxis.architect import design_interventions, redesign_interventions, fallback_interventions
from praxis.business_case import score_interventions
from praxis.skeptic import review, ground_verdicts
from praxis.principal import assemble_deliverable
from praxis.analyst import serialize_map
from praxis.firm_agent import study_firm, morph_firm


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


async def _deliberate_hard(client, model, opportunities, firm, state):
    """Collaborative product-determination for the HIGH-BURDEN core work — the hard, high-value
    steps the architect tends to fumble when designing alone (e.g. 'edit thousands of photos').
    The architect and skeptic CONVERGE per opportunity: architect proposes -> skeptic challenges
    -> architect refines addressing that specific challenge -> (skeptic re-checks). Each builds on
    the other's reasoning instead of working in isolation. Returns {step_label: intervention}.
    Bounded to a few hard opportunities so the collaboration doesn't explode the call budget."""
    from praxis.grounding import measure_burden, burden_severity
    hard = [o for o in opportunities
            if burden_severity(measure_burden(o.step_label, model)) == "high"][:4]
    strong = {}
    for opp in hard:
        proposed = await _attempt(
            lambda: design_interventions(client, model, [opp], _mem(firm, "architect")))
        if not proposed:
            continue
        iv = proposed[0]
        # Skeptic challenges the proposal in the room (not after the fact).
        verdicts = await review(client, [iv], [], _mem(firm, "skeptic"))
        v = verdicts[0] if verdicts else None
        rounds = 0
        while v and v.verdict != "solid" and v.objection and rounds < 2:
            revised = await _attempt(lambda: redesign_interventions(
                client, model, [opp], {opp.step_label: v.objection}, _mem(firm, "architect")))
            if not revised:
                break
            iv = revised[0]
            state.record("architect", "deliberated_with_skeptic",
                         f"refined '{opp.step_label}' after the skeptic's challenge: "
                         f"{v.objection[:60]}", consumed_from="skeptic")
            verdicts = await review(client, [iv], [], _mem(firm, "skeptic"))
            v = verdicts[0] if verdicts else None
            rounds += 1
        strong[opp.step_label] = iv
    return strong


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
        # Owned floor: an empty Analyst return on a real map is a failure of the call, not a
        # truth about the business — a client must never receive an empty plan. Build
        # opportunities directly from the measured graph and say so in the record.
        opportunities = fallback_opportunities(model)
        state.opportunities = opportunities
        state.record("analyst", "fallback_opportunities",
                     f"analyst returned none on a real map — built {len(opportunities)} "
                     "from measured burden instead",
                     consumed_from="discovery", count=len(opportunities))
    if not opportunities:
        # Truly nothing (no evidenced steps at all) — only then may the plan be empty.
        state.deliverable = assemble_deliverable(model, [], [], [], [])
        state.record("principal", "assembled_deliverable", "no opportunities found")
        return state

    # Collaborative pass FIRST on the hard, high-burden core work: architect + skeptic converge
    # on those so they aren't fumbled by the architect designing alone.
    strong = await _deliberate_hard(client, model, opportunities, firm, state) if firm else {}
    if strong:
        state.record("architect+skeptic", "deliberated",
                     f"converged on {len(strong)} high-burden interventions together",
                     consumed_from="analyst", count=len(strong))

    interventions = await _attempt(
        lambda: design_interventions(client, model, opportunities, _mem(firm, "architect")))
    # The deliberated versions win over the one-shot batch designs for the hard steps.
    interventions = [strong.get(iv.step_label, iv) for iv in interventions]
    # Backstop: opportunities existed but design came back empty (a truncation/stochastic
    # failure) — never let that silently empty the plan. Build bare interventions to recommend.
    if not interventions:
        interventions = list(strong.values()) or fallback_interventions(opportunities)
        state.record("architect", "fallback_interventions",
                     f"design returned none on {len(opportunities)} real opportunities — "
                     f"built {len(interventions)} bare interventions instead",
                     consumed_from="analyst", count=len(interventions))
    state.interventions = interventions
    state.record("architect", "designed_interventions",
                 f"designed {len(interventions)} interventions "
                 f"({len(strong)} via architect+skeptic deliberation)",
                 consumed_from="analyst", count=len(interventions))

    assessments = await _attempt(
        lambda: score_interventions(client, interventions, _mem(firm, "business_case")))
    state.assessments = assessments
    state.record("business_case", "scored", f"scored {len(assessments)} interventions",
                 consumed_from="architect", count=len(assessments))

    verdicts = await _attempt(
        lambda: review(client, interventions, assessments, _mem(firm, "skeptic")))
    verdicts = ground_verdicts(verdicts, model)   # overturn invented-preference rejections of core work
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
        verdicts = ground_verdicts(verdicts, model)
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
