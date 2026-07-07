"""The Analyst: reads a Discovery workflow map and marks AI-opportunity points —
places where AI could remove manual effort or friction. Each opportunity is anchored to a
specific step and the client's own words. The lens is a content-free taxonomy of what AI is
good at (never a business template), so it stays Ocean-safe. The Analyst only IDENTIFIES
opportunities; it does not design the solution (Architect) or score them (Business-case)."""
import json
from dataclasses import dataclass
from praxis.models import NodeType, EdgeType

CAPABILITIES = [
    "automate manual data transfer between tools",
    "extract structured data from documents or emails",
    "draft or generate text (proposals, replies, summaries)",
    "summarize or synthesize information",
    "classify, route, or triage items",
    "flag, predict, or detect (anomalies, churn, risk)",
    "answer questions or look up information over their own data",
]

ANALYST_SYSTEM = (
    "You are an AI-implementation analyst. You are given ONE business's real workflow map "
    "(steps, who does them, tools, inputs, outputs, friction, and what the owner said). "
    "Find the places where AI could genuinely remove manual effort or friction.\n\n"
    "Judge each step ONLY against what AI is actually good at:\n"
    + "\n".join(f"- {c}" for c in CAPABILITIES)
    + "\n\nReturn JSON {\"opportunities\": [ {\"step_label\": \"<an EXACT step label from "
    "the map>\", \"capability\": \"<one capability from the list above, verbatim>\", "
    "\"description\": \"<specific to THIS business, in their terms>\", \"evidence\": \"<the "
    "exact phrase from the map that shows the manual effort or friction>\"} ] }.\n\n"
    "Rules:\n"
    "- Only mark an opportunity where the owner described a CLEAR, real, repeated pain or "
    "manual grind. Do NOT reach for AI just because a step COULD be automated — if the pain is "
    "mild, one-off, or you are assuming it, leave it out.\n"
    "- Every opportunity MUST reference an exact step_label and quote the evidence that shows "
    "the pain. No quote, no opportunity.\n"
    "- Be selective: a few strongly-evidenced opportunities beat a long list. Prefer the 2-4 "
    "clearest pains over covering everything.\n"
    "- Be specific to THIS business, not generic advice. Do NOT design the solution or estimate "
    "ROI — only identify WHERE AI fits and WHY."
)


@dataclass
class Opportunity:
    step_label: str
    capability: str
    description: str
    evidence: str


def serialize_map(model) -> str:
    """Render the workflow map as compact text the Analyst can reason over."""
    nid = model.nodes
    lines = []

    def labels(ids):
        return ", ".join(nid[i].label for i in ids if i in nid)

    for s in model.nodes_of(NodeType.STEP):
        outs = model.edges_from(s.id)
        ins = [e for e in model.edges.values() if e.target == s.id]
        parts = [f"step: {s.label}"]
        actor = labels([e.source for e in ins if e.type == EdgeType.PERFORMS])
        tool = labels([e.target for e in outs if e.type == EdgeType.USES])
        inp = labels([e.target for e in outs if e.type == EdgeType.CONSUMES])
        outp = labels([e.target for e in outs if e.type == EdgeType.PRODUCES])
        fr = labels([e.target for e in outs if e.type == EdgeType.CAUSES])
        if actor:
            parts.append(f"who={actor}")
        if tool:
            parts.append(f"tool={tool}")
        if inp:
            parts.append(f"input={inp}")
        if outp:
            parts.append(f"output={outp}")
        if fr:
            parts.append(f"friction={fr}")
        if s.evidence:
            parts.append(f'said="{s.evidence[0].quote}"')
        lines.append("; ".join(parts))
    return "\n".join(lines)


async def find_opportunities(client, model):
    """Return evidence-anchored Opportunity objects for a Discovery workflow map."""
    step_labels = {s.label for s in model.nodes_of(NodeType.STEP)}
    if not step_labels:
        return []
    result = await client.complete_json(ANALYST_SYSTEM, serialize_map(model),
                                        max_tokens=2048)
    out = []
    for o in (result.get("opportunities", []) if isinstance(result, dict) else []):
        if not isinstance(o, dict):
            continue
        label = o.get("step_label")
        evidence = (o.get("evidence") or "").strip()
        description = (o.get("description") or "").strip()
        # Anchor rule: must point at a real step and carry evidence + a description.
        if label in step_labels and evidence and description:
            out.append(Opportunity(label, (o.get("capability") or "").strip(),
                                    description, evidence))
    return out
