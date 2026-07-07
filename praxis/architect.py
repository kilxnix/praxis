"""The Architect: designs a concrete AI intervention for each opportunity the Analyst
found. Specific to the client's own tools and steps (Ocean-safe). It designs only — it does
not score/prioritize (Business-case) or build the automation (SP2, the Build Wing)."""
from dataclasses import dataclass
from praxis.analyst import serialize_map

ARCHITECT_SYSTEM = (
    "You are an AI-implementation architect. You are given a business's workflow map and a "
    "list of AI-opportunity points already found in it. Design ONE concrete, minimal AI "
    "intervention for each opportunity.\n\n"
    "For each, describe in plain language, specific to THEIR tools and step:\n"
    "- what_it_does: the concrete AI action\n"
    "- where_it_plugs_in: which existing step or tool it hooks into\n"
    "- inputs_needed: what data or access it requires to work\n"
    "- changes_for_people: what changes for the person who does that step\n\n"
    "Return JSON {\"interventions\": [ {\"step_label\": \"<exact step from the opportunity>\", "
    "\"what_it_does\": \"..\", \"where_it_plugs_in\": \"..\", \"inputs_needed\": \"..\", "
    "\"changes_for_people\": \"..\"} ] }.\n"
    "Be specific to their actual tools. Address ONLY the one opportunity — do NOT invent "
    "adjacent features, approval workflows, or automation the owner never mentioned. If the "
    "owner values doing a step themselves, keep them in control (assist, don't replace it). "
    "Keep each intervention minimal, grounded, and practical. Do NOT estimate ROI or rank them."
)


@dataclass
class Intervention:
    step_label: str
    what_it_does: str
    where_it_plugs_in: str
    inputs_needed: str
    changes_for_people: str


def _serialize_opps(opportunities):
    return "\n".join(
        f"- step '{o.step_label}' [{o.capability}]: {o.description}"
        for o in opportunities
    )


REDESIGN_SYSTEM = (
    "You are an AI-implementation architect. A skeptic REJECTED or flagged your previous "
    "intervention designs for specific steps. Redesign each one to directly ADDRESS the "
    "objection. If the objection is that it forces the business to change how they work "
    "(an Ocean-Principle violation), propose a smaller, safer intervention that fits how "
    "they ACTUALLY operate — or a human-in-the-loop version.\n\n"
    "For each, give what_it_does, where_it_plugs_in, inputs_needed, changes_for_people, "
    "specific to their tools.\n\n"
    "Return JSON {\"interventions\": [ {\"step_label\": \"<exact step>\", \"what_it_does\": "
    "\"..\", \"where_it_plugs_in\": \"..\", \"inputs_needed\": \"..\", \"changes_for_people\": "
    "\"..\"} ] }."
)


def _text(v):
    """Coerce an LLM field to a clean string. The model sometimes returns a list (e.g.
    inputs_needed: ["camera", "photo access"]) where we expect prose; join rather than crash."""
    if isinstance(v, list):
        return "; ".join(_text(x) for x in v if x is not None).strip()
    if v is None:
        return ""
    return str(v).strip()


def _parse_interventions(result, allowed_steps):
    out, seen = [], set()
    for iv in (result.get("interventions", []) if isinstance(result, dict) else []):
        if not isinstance(iv, dict):
            continue
        label = iv.get("step_label")
        what = _text(iv.get("what_it_does"))
        if label in allowed_steps and what and label not in seen:
            seen.add(label)
            out.append(Intervention(
                label, what,
                _text(iv.get("where_it_plugs_in")),
                _text(iv.get("inputs_needed")),
                _text(iv.get("changes_for_people")),
            ))
    return out


async def design_interventions(client, model, opportunities):
    """One intervention per opportunity, anchored to the opportunity's step."""
    if not opportunities:
        return []
    opp_steps = {o.step_label for o in opportunities}
    user = ("WORKFLOW MAP:\n" + serialize_map(model)
            + "\n\nOPPORTUNITIES:\n" + _serialize_opps(opportunities))
    result = await client.complete_json(ARCHITECT_SYSTEM, user, max_tokens=2048)
    return _parse_interventions(result, opp_steps)


async def redesign_interventions(client, model, opportunities, objections):
    """Redesign flagged interventions to address the Skeptic's objections (the bounce-back)."""
    if not opportunities:
        return []
    opp_steps = {o.step_label for o in opportunities}
    obj_lines = "\n".join(
        f"- step '{o.step_label}': objection was: {objections.get(o.step_label) or '(flagged, weak)'}"
        for o in opportunities
    )
    user = ("WORKFLOW MAP:\n" + serialize_map(model)
            + "\n\nFLAGGED OPPORTUNITIES + THE SKEPTIC'S OBJECTIONS:\n" + obj_lines)
    result = await client.complete_json(REDESIGN_SYSTEM, user, max_tokens=2048)
    return _parse_interventions(result, opp_steps)
