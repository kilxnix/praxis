"""The Analyst: reads a Discovery workflow map and marks AI-opportunity points —
places where AI could remove manual effort or friction. Each opportunity is anchored to a
specific step and the client's own words. The lens is a content-free taxonomy of what AI is
good at (never a business template), so it stays Ocean-safe. The Analyst only IDENTIFIES
opportunities; it does not design the solution (Architect) or score them (Business-case)."""
import json
from dataclasses import dataclass, replace
from praxis.models import NodeType, EdgeType
from praxis.grounding import measure_grounding, measure_burden, burden_severity
from praxis.discovery_signals import canonical_label

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
    "The 'evidence' you give MUST be an exact phrase the owner actually said (copy it from the "
    "map's said=\"...\" text or a node label). Do not paraphrase or invent it — a downstream "
    "check measures whether your evidence really appears in their words, and anything invented "
    "is discarded. So only raise an opportunity you can back with their real words.\n\n"
    "Return JSON {\"opportunities\": [ {\"step_label\": \"<an EXACT step label from "
    "the map>\", \"capability\": \"<one capability from the list above, verbatim>\", "
    "\"description\": \"<specific to THIS business, in their terms>\", \"evidence\": \"<the "
    "exact phrase THEY said that shows the manual effort or friction>\", \"severity\": "
    "\"high|medium|low\"} ] }.\n\n"
    "Rules:\n"
    "- Find ALL the real opportunities across the workflow — don't stop at one. But every "
    "opportunity MUST address something the owner actually does (not an assumption) and quote "
    "the evidence that shows the manual effort or friction. No quote, no opportunity.\n"
    "- Rate severity HONESTLY — later stages use it to focus on the biggest pains, so you don't "
    "pre-filter; just be truthful about which pains are big vs. minor.\n"
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


def _resolve_step_label(raw, step_labels, by_canon):
    """Map the model's echo of a step label back to the REAL step. Exact, then canonical
    (absorbs case/punctuation/articles), then unique containment ('cross-reference records' for
    'cross-reference records against spreadsheet'). Exact string-matching here silently discarded
    every opportunity when the model reworded a label — an 8-step map came back with 0
    opportunities three retries in a row, shipping an EMPTY deliverable."""
    if raw in step_labels:
        return raw
    c = canonical_label(raw or "")
    if not c:
        return None
    if c in by_canon:
        return by_canon[c]
    contains = [s for k, s in by_canon.items() if c in k or k in c]
    return contains[0] if len(contains) == 1 else None


def _parse_opportunities(result, step_labels):
    by_canon = {canonical_label(s): s for s in step_labels}
    out = []
    for o in (result.get("opportunities", []) if isinstance(result, dict) else []):
        if not isinstance(o, dict):
            continue
        label = _resolve_step_label(o.get("step_label"), step_labels, by_canon)
        evidence = (o.get("evidence") or "").strip()
        description = (o.get("description") or "").strip()
        severity = (o.get("severity") or "").strip().lower()
        severity = severity if severity in ("high", "medium", "low") else "medium"
        grounding = (o.get("grounding") or "").strip().lower()
        grounding = grounding if grounding in GROUNDINGS else "recurring"
        # Anchor rule: must point at a real step and carry evidence + a description.
        if label and evidence and description:
            out.append(Opportunity(label, (o.get("capability") or "").strip(),
                                    description, evidence, severity, grounding))
    return out


async def find_opportunities(client, model, memory_text=""):
    """Return evidence-anchored Opportunity objects for a Discovery workflow map. If the analyst
    sat in on the interview, they reason from what they came to understand (memory_text).

    The Analyst on a local model is lazy — it returns 1 opportunity from a 7-step map full of
    obvious drudgery. So we structurally enforce coverage: after the first pass, re-prompt for
    any step it IGNORED (each must get an opportunity OR an explicit 'no AI fit'), and dedup so
    the same step can't be flagged twice."""
    steps = model.nodes_of(NodeType.STEP)
    step_labels = {s.label for s in steps}
    if not step_labels:
        return []
    prefix = ""
    if memory_text:
        prefix = ("WHAT YOU CAME TO UNDERSTAND SITTING IN ON THIS BUSINESS'S INTERVIEW "
                  "(reason from this, not just the map below):\n" + memory_text + "\n\n")
    map_text = serialize_map(model)

    result = await client.complete_json(ANALYST_SYSTEM, prefix + "THE WORKFLOW MAP:\n" + map_text,
                                        max_tokens=2048)
    by_step = {}      # step_label -> Opportunity (first wins; dedup)
    examined = set()
    for o in _parse_opportunities(result, step_labels):
        by_step.setdefault(o.step_label, o)
        examined.add(o.step_label)

    # Coverage passes: force the Analyst to look at the steps it skipped. A step it examines and
    # legitimately finds no fit for is marked examined (via "no_fit"), so we don't loop on it.
    for _ in range(2):
        unexamined = [s.label for s in steps if s.label not in examined]
        if not unexamined:
            break
        user = (prefix + "THE WORKFLOW MAP:\n" + map_text
                + "\n\nYou did NOT evaluate these steps. For EACH one, either give an opportunity "
                "(same JSON shape) OR mark it done with {\"step_label\":\"..\",\"no_fit\":true} if "
                "there is genuinely no AI fit. Do not ignore any:\n"
                + "\n".join(f"- {lbl}" for lbl in unexamined))
        result = await client.complete_json(ANALYST_SYSTEM, user, max_tokens=2048)
        for o in _parse_opportunities(result, step_labels):
            by_step.setdefault(o.step_label, o)
            examined.add(o.step_label)
        # steps the Analyst explicitly cleared as no-fit are examined too
        for o in (result.get("opportunities", []) if isinstance(result, dict) else []):
            if isinstance(o, dict) and o.get("no_fit") and o.get("step_label") in step_labels:
                examined.add(o.get("step_label"))

    # OWNED PRIORITY: never let the Analyst dismiss the HIGH-BURDEN core work (the owner's own
    # words flag heavy volume/time there) while it flags admin busywork. Force an opportunity for
    # any high-burden step it skipped — no_fit is not allowed on the work that costs them most.
    for _ in range(2):
        heavy = [s.label for s in steps if s.label not in by_step
                 and burden_severity(measure_burden(s.label, model)) == "high"]
        if not heavy:
            break
        user = (prefix + "THE WORKFLOW MAP:\n" + map_text
                + "\n\nThese steps cost the owner heavy VOLUME or TIME (their own words). There IS "
                "a real AI opportunity in each — describe ONE per step, do NOT skip or dismiss "
                "any:\n" + "\n".join(f"- {lbl}" for lbl in heavy))
        result = await client.complete_json(ANALYST_SYSTEM, user, max_tokens=2048)
        for o in _parse_opportunities(result, step_labels):
            by_step.setdefault(o.step_label, o)

    # OWNED JUDGMENT: the model decides neither grounding NOR priority. Measure both from the
    # owner's own recorded words and overwrite the model's self-labels.
    ordered = [by_step[s.label] for s in steps if s.label in by_step]
    return [replace(o, grounding=measure_grounding(o, model),
                    severity=burden_severity(measure_burden(o.step_label, model)))
            for o in ordered]


def fallback_opportunities(model, max_n=4):
    """Owned floor: the firm never ships an EMPTY plan while the map holds real, evidenced
    steps. If the Analyst comes up empty (a stochastic/parse failure, not a truth about the
    business), build opportunities directly from the graph — the top steps by MEASURED burden,
    each anchored to the owner's own quote. The capability text is generic on purpose; the
    Architect designs the specifics. Recorded transparently by the caller."""
    scored = []
    for s in model.nodes_of(NodeType.STEP):
        if s.evidence:
            scored.append((measure_burden(s.label, model), s))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = []
    for b, s in scored[:max_n]:
        opp = Opportunity(s.label, "remove the manual effort in this step",
                          f"lift the manual burden of '{s.label}'",
                          s.evidence[0].quote, burden_severity(b))
        out.append(replace(opp, grounding=measure_grounding(opp, model)))
    return out


def passes_evidence_bar(opp):
    """The judgment gate — decided on MEASURED grounding (praxis.grounding), not the model's word.
    - weak:      the anchor isn't substantiated by anything the owner actually said — an invented,
                 capability-driven guess. Always dropped; this is the real filter the critique
                 demanded ('driven by available AI, not by what they described').
    - one_off:   a single, non-emphasized mention. Kept UNLESS it's also low severity — a trivial
                 anecdote. (Severity-based selection downstream keeps it from leading the plan.)
    - recurring: a real, repeated / emphasized pain. Always clears.
    """
    if opp.grounding == "weak":
        return False
    if opp.grounding == "one_off" and opp.severity == "low":
        return False
    return True


def apply_evidence_bar(opportunities):
    """Return (kept, dropped). Kept opportunities are what the firm designs for; dropped ones
    are recorded so the gate is transparent, never a silent truncation."""
    kept, dropped = [], []
    for o in opportunities:
        (kept if passes_evidence_bar(o) else dropped).append(o)
    return kept, dropped
