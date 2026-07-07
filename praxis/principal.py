"""The Principal: assembles the finished deliverable from everything the firm produced.
Deterministic assembly (no LLM — reliable) into the five sections from the SP1 spec:
the workflow mirrored back, where it hurts, where AI fits (prioritized, rejects removed),
the rollout, and what we're NOT recommending (with the Skeptic's objections)."""
from praxis.models import NodeType, EdgeType
from praxis.business_case import _PRIORITY_ORDER


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
        rejected = (v is not None and v.verdict == "reject") or \
                   (a is not None and a.priority == "skip")
        if rejected:
            reason = (v.objection if (v and v.objection)
                      else (a.rationale if a else "not worth the effort"))
            not_recommending.append({"step": iv.step_label, "reason": reason})
            continue
        entry = {
            "step": iv.step_label,
            "what_it_does": iv.what_it_does,
            "where_it_plugs_in": iv.where_it_plugs_in,
            "inputs_needed": iv.inputs_needed,
            "changes_for_people": iv.changes_for_people,
            "priority": a.priority if a else "worth it",
            "effort": a.effort if a else "medium",
            "time_saved": a.time_saved if a else "medium",
            "risk": a.risk if a else "medium",
        }
        if v is not None and v.verdict == "weak" and v.objection:
            entry["caveat"] = v.objection      # unresolved Skeptic objection carried forward
        recommended.append(entry)

    recommended.sort(key=lambda e: _PRIORITY_ORDER.get(e["priority"], 1))  # quick wins first

    return {
        "workflow_mirror": workflow_mirror,
        "where_it_hurts": where_it_hurts,
        "where_ai_fits": recommended,
        "rollout": [e["step"] for e in recommended],
        "not_recommending": not_recommending,
    }
