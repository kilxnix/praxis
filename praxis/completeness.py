"""Discovery completeness gate. Before the interview concludes, judge whether the WHOLE job
is mapped — beginning to end — instead of trusting the crude 'no new step for a while, so
we must be done' heuristic. If a phase is missing, it says what to probe next so the
interviewer can go get it."""
from praxis.models import NodeType

COMPLETENESS_SYSTEM = (
    "You are checking whether a business's workflow has been mapped from beginning to end. "
    "You are given the steps captured so far, in order. A COMPLETE map covers the whole job: "
    "how the work ARRIVES, the CORE work itself, any HANDOFFS between people or tools, and how "
    "it FINISHES (delivery, billing, follow-up).\n\n"
    "If a major phase of THIS job is clearly missing, it is NOT complete — say briefly, in "
    "plain terms, what to ask about next. If the arc is genuinely covered start to finish, mark "
    "it complete. Judge only from the steps given; don't invent phases a business like this "
    "wouldn't have.\n\n"
    "Return JSON {\"complete\": true|false, \"missing\": \"<short hint of what to ask about "
    "next; empty if complete>\"}."
)


async def assess_completeness(client, model):
    """Return {'complete': bool, 'missing': str}. Defaults to complete on an unclear/empty
    LLM result so it fails safe toward stopping (never loops forever)."""
    steps = [s.label for s in model.nodes_of(NodeType.STEP)]
    if len(steps) < 2:
        return {"complete": False, "missing": "how the work starts"}
    user = ("STEPS MAPPED SO FAR (in order):\n"
            + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)))
    result = await client.complete_json(COMPLETENESS_SYSTEM, user, max_tokens=256)
    if not isinstance(result, dict):
        return {"complete": True, "missing": ""}
    return {"complete": bool(result.get("complete", True)),
            "missing": (result.get("missing") or "").strip()}
