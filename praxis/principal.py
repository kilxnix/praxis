"""The Principal: assembles the deliverable AND speaks it in a human voice.
Two parts:
- assemble_deliverable: deterministic structure (workflow mirror, where AI fits [prioritized,
  rejects removed], rollout, what we're NOT recommending) — reliable, no LLM.
- synthesize: an LLM pass that turns the technical map+interventions into what a NON-TECHNICAL
  owner actually cares about — plain-language pains, a warm summary, and outcome-framed
  recommendations. This is where the firm stops sounding like an architect and starts sounding
  like a consultant."""
import json
from praxis.models import NodeType, EdgeType
from praxis.business_case import _PRIORITY_ORDER

SYNTHESIS_SYSTEM = (
    "You are the lead consultant writing the summary a NON-TECHNICAL small-business owner "
    "will read. You are given the interview transcript (their own words) and the recommended "
    "steps written in technical language. Translate it into what they actually care about.\n\n"
    "Produce:\n"
    "1. pains: 3-6 plain-language pain points they FEEL day to day, drawn from what they said. "
    "Include the DEEPER ones, not just tasks: the constant switching between many tools, the "
    "mental load of tracking status in their head across email/spreadsheet/Trello/Slack, having "
    "to remember to check things all day, and specific tasks like copying leads by hand. Short "
    "phrases in their world.\n"
    "2. summary: 2-3 warm, plain sentences — what's eating their time and what would change.\n"
    "3. outcomes: for each recommended step, ONE plain-language outcome ('You stop manually "
    "copying every lead into the sheet'), NOT how it's built.\n\n"
    "STRICT: no jargon. Never say API, integration, IMAP, webhook, Zapier, sync, parse, or "
    "trigger. Talk about their day, their time, their leads.\n"
    "Return JSON {\"summary\": \"..\", \"pains\": [\"..\"], \"outcomes\": [{\"step\": \"<exact "
    "step>\", \"outcome\": \"..\"}]}."
)


def _step_friction(model, step_id):
    nid = model.nodes
    return [nid[e.target].label for e in model.edges_from(step_id)
            if e.type == EdgeType.CAUSES and e.target in nid]


def assemble_deliverable(model, opportunities, interventions, assessments, verdicts):
    verdict_by = {v.step_label: v for v in verdicts}
    score_by = {a.step_label: a for a in assessments}

    steps = model.nodes_of(NodeType.STEP)
    workflow_mirror = [s.label for s in steps]
    where_it_hurts = [{"step": s.label, "friction": fr}
                      for s in steps if (fr := _step_friction(model, s.id))]

    recommended, not_recommending = [], []
    for iv in interventions:
        v = verdict_by.get(iv.step_label)
        a = score_by.get(iv.step_label)
        # Only SOLID interventions are recommended. A weak verdict (a real, unresolved concern)
        # or a 'skip' is set aside with its reason — we never ship a recommendation that our
        # own review says makes things worse.
        set_aside = (v is not None and v.verdict in ("reject", "weak")) or \
                    (a is not None and a.priority == "skip")
        if set_aside:
            reason = (v.objection if (v and v.objection)
                      else (a.rationale if a else "not clearly worth it"))
            not_recommending.append({"step": iv.step_label, "reason": reason})
            continue
        recommended.append({
            "step": iv.step_label,
            "what_it_does": iv.what_it_does,
            "where_it_plugs_in": iv.where_it_plugs_in,
            "inputs_needed": iv.inputs_needed,
            "changes_for_people": iv.changes_for_people,
            "priority": a.priority if a else "worth it",
            "effort": a.effort if a else "medium",
            "time_saved": a.time_saved if a else "medium",
            "risk": a.risk if a else "medium",
        })

    recommended.sort(key=lambda e: _PRIORITY_ORDER.get(e["priority"], 1))  # quick wins first

    return {
        "workflow_mirror": workflow_mirror,
        "where_it_hurts": where_it_hurts,
        "where_ai_fits": recommended,
        "rollout": [e["step"] for e in recommended],
        "not_recommending": not_recommending,
    }


def _client_turns(transcript):
    return "\n".join(t.get("content", "") for t in transcript if t.get("role") == "user")


async def synthesize(client, transcript, deliverable):
    """Enrich the deliverable with owner-facing pains, a human summary, and per-step
    outcomes. Reliability: on any failure the deliverable is returned unchanged."""
    recs = deliverable.get("where_ai_fits", [])
    if not transcript and not recs:
        return deliverable
    rec_lines = "\n".join(f"- step '{e['step']}': {e['what_it_does']}" for e in recs)
    user = ("WHAT THE OWNER SAID:\n" + _client_turns(transcript)[:4000]
            + "\n\nRECOMMENDED STEPS (technical wording to translate):\n" + rec_lines)
    result = await client.complete_json(SYNTHESIS_SYSTEM, user, max_tokens=1536)
    if not isinstance(result, dict):
        return deliverable
    summary = (result.get("summary") or "").strip()
    if summary:
        deliverable["summary"] = summary
    pains = [p.strip() for p in result.get("pains", []) if isinstance(p, str) and p.strip()]
    if pains:
        deliverable["pains"] = pains
    outcome_by = {o.get("step"): (o.get("outcome") or "").strip()
                  for o in result.get("outcomes", []) if isinstance(o, dict)}
    for e in recs:
        if outcome_by.get(e["step"]):
            e["outcome"] = outcome_by[e["step"]]
    return deliverable
