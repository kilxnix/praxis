"""The Analyst: reads a Discovery workflow map and marks AI-opportunity points —
places where AI could remove manual effort or friction. Each opportunity is anchored to a
specific step and the client's own words. The lens is a content-free taxonomy of what AI is
good at (never a business template), so it stays Ocean-safe. The Analyst only IDENTIFIES
opportunities; it does not design the solution (Architect) or score them (Business-case)."""
import json
from dataclasses import dataclass
from praxis.models import NodeType, EdgeType

CAPABILITIES = [
    "automate moving data between tools (copy-paste, re-keying)",
    "extract structured details from documents, forms, emails, or images",
    "transcribe and summarize calls, meetings, or spoken notes",
    "draft or generate text (replies, reports, proposals, notes)",
    "summarize or synthesize information from many sources",
    "answer questions or look things up across their own records",
    "classify, route, tag, or triage incoming items",
    "check work for errors, omissions, or compliance issues",
    "analyze photos, scans, or images (inspect, measure, compare)",
    "flag, predict, or detect risks (anomalies, delays, churn, safety)",
    "schedule, coordinate, or sequence work and appointments",
    "guide someone through a complex procedure step by step",
    "translate or reformat content for a different audience",
]

ANALYST_SYSTEM = (
    "You are an AI-implementation analyst. You are given ONE business's real workflow map "
    "(steps, who does them, tools, inputs, outputs, friction, and what the owner said). "
    "Find the places where AI could genuinely remove manual effort or friction.\n\n"
    "Judge each step ONLY against what AI is actually good at:\n"
    + "\n".join(f"- {c}" for c in CAPABILITIES)
    + "\n\nDifferent kinds of work lean on different capabilities — a business built on phone "
    "calls benefits from transcription, one handling photos or site visits from image analysis, "
    "one juggling appointments from scheduling, one reviewing documents from checking for errors. "
    "Match THEIR real work to the best-fitting capability; don't default to data-entry.\n\n"
    "For each, also rate SEVERITY — how big a pain this is TO THE OWNER, judged by how "
    "much they emphasized it, how often it comes up, and how much time/worry it causes: "
    "'high' (a top pain they clearly feel), 'medium', or 'low' (minor).\n\n"
    "And rate GROUNDING — how well what THEY SAID supports this being a real, worth-solving "
    "problem (be strict and honest; this is a filter):\n"
    "- 'recurring': they described it as something that happens repeatedly / every time / as "
    "part of their routine, or they clearly emphasized it as a real pain.\n"
    "- 'one_off': a single vivid anecdote or a thing mentioned once in passing — it happened, "
    "but there's no sign it's a recurring pattern.\n"
    "- 'weak': you're inferring it mostly because AI *could* help there, not because they "
    "actually described friction. If you're reaching, say 'weak' — do not dress it up.\n\n"
    "Return JSON {\"opportunities\": [ {\"step_label\": \"<an EXACT step label from "
    "the map>\", \"capability\": \"<one capability from the list above, verbatim>\", "
    "\"description\": \"<specific to THIS business, in their terms>\", \"evidence\": \"<the "
    "exact phrase from the map that shows the manual effort or friction>\", \"severity\": "
    "\"high|medium|low\", \"grounding\": \"recurring|one_off|weak\"} ] }.\n\n"
    "Rules:\n"
    "- Find ALL the real opportunities across the workflow — don't stop at one. But every "
    "opportunity MUST address something the owner actually does (not an assumption) and quote "
    "the evidence that shows the manual effort or friction. No quote, no opportunity.\n"
    "- Rate severity and grounding HONESTLY (see above) — later stages use them to focus on the "
    "biggest, best-supported pains, so you don't pre-filter; just be truthful. Do not inflate a "
    "one-off into 'recurring' or a guess into a real pain.\n"
    "- Be specific to THIS business, not generic advice. Do NOT design the solution or estimate "
    "ROI — only identify WHERE AI fits and WHY."
)

GROUNDINGS = ("recurring", "one_off", "weak")


@dataclass
class Opportunity:
    step_label: str
    capability: str
    description: str
    evidence: str
    severity: str = "medium"      # how big a pain this is to the owner: high | medium | low
    grounding: str = "recurring"  # how well their words support it: recurring | one_off | weak


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


async def find_opportunities(client, model, memory_text=""):
    """Return evidence-anchored Opportunity objects for a Discovery workflow map. If the analyst
    sat in on the interview, they reason from what they came to understand (memory_text), not
    just the flattened map."""
    step_labels = {s.label for s in model.nodes_of(NodeType.STEP)}
    if not step_labels:
        return []
    user = serialize_map(model)
    if memory_text:
        user = ("WHAT YOU CAME TO UNDERSTAND SITTING IN ON THIS BUSINESS'S INTERVIEW "
                "(reason from this, not just the map below):\n" + memory_text
                + "\n\nTHE WORKFLOW MAP:\n" + user)
    result = await client.complete_json(ANALYST_SYSTEM, user, max_tokens=2048)
    out = []
    for o in (result.get("opportunities", []) if isinstance(result, dict) else []):
        if not isinstance(o, dict):
            continue
        label = o.get("step_label")
        evidence = (o.get("evidence") or "").strip()
        description = (o.get("description") or "").strip()
        severity = (o.get("severity") or "").strip().lower()
        severity = severity if severity in ("high", "medium", "low") else "medium"
        grounding = (o.get("grounding") or "").strip().lower()
        grounding = grounding if grounding in GROUNDINGS else "recurring"
        # Anchor rule: must point at a real step and carry evidence + a description.
        if label in step_labels and evidence and description:
            out.append(Opportunity(label, (o.get("capability") or "").strip(),
                                    description, evidence, severity, grounding))
    return out


def passes_evidence_bar(opp):
    """The judgment gate the critique demanded: distinguish real, recurring friction from a
    one-off anecdote or a capability-driven guess, BEFORE anything gets designed.
    - recurring: always clears — it's a real, repeated pain.
    - one_off:   clears ONLY if severe (a rare but catastrophic pain is still worth solving);
                 otherwise it's an anecdote, not a plan item.
    - weak:      never clears — it's 'AI could help here', not a pain they described.
    """
    if opp.grounding == "recurring":
        return True
    if opp.grounding == "one_off":
        return opp.severity == "high"
    return False


def apply_evidence_bar(opportunities):
    """Return (kept, dropped). Kept opportunities are what the firm designs for; dropped ones
    are recorded so the gate is transparent, never a silent truncation."""
    kept, dropped = [], []
    for o in opportunities:
        (kept if passes_evidence_bar(o) else dropped).append(o)
    return kept, dropped
