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
    "adjacent features, approval workflows, or automation the owner never mentioned.\n\n"
    "MEANINGFULLY reduce the burden. Each intervention must actually LIFT the manual drudgery "
    "off this step — the re-typing, transcribing, copying, scribbling the owner complains about. "
    "A change that leaves them doing almost as much work (e.g. 'you just sign off on what's "
    "written', 'it captures your scribble so you can still type it later') is TOO TIMID and "
    "fails. Remove the manual effort, don't decorate it.\n"
    "Keep the owner in control of the JUDGMENT they value (which client, the diagnosis, the "
    "final decision) — but do NOT preserve the manual data-entry drudgery they resent just "
    "because it's their current habit. Respect their decisions; lift their busywork.\n"
    "Keep each intervention grounded and practical. Do NOT estimate ROI or rank them.\n\n"
    "CRITICAL: design an intervention for EVERY opportunity you are given — one per opportunity, "
    "no exceptions. Do NOT skip, drop, or decline one because it feels too aggressive, premature, "
    "or risky. Deciding whether a change is worth it or too risky is the skeptic's and "
    "business-case's job, not yours. If a change feels risky or heavy, design a SMALLER, "
    "human-in-the-loop, or deferred version of it — but still design it. Your caution shapes HOW "
    "you design each intervention, never WHETHER you design it. The number of interventions you "
    "return must equal the number of opportunities you were given."
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


BOLDEN_SYSTEM = (
    "You are an AI-implementation architect. Your previous design for a step was TOO TIMID — it "
    "left the owner doing almost as much manual work as before (it stays inert, only 'assists', "
    "hands back an empty document, or still makes them type/transcribe/copy). That fails: the "
    "point is to LIFT the drudgery off them.\n\n"
    "Redesign it to actually REMOVE the manual busywork on this step — do the transcription, the "
    "data entry, the copying, the drafting FOR them — while keeping them in control of the "
    "JUDGMENT they value (the final decision, the diagnosis, who to serve): they review and "
    "approve, they don't re-do the work. Concrete, specific to their tools, genuinely less work "
    "for them.\n\n"
    "Return JSON {\"interventions\": [ {\"step_label\": \"<exact step>\", \"what_it_does\": "
    "\"..\", \"where_it_plugs_in\": \"..\", \"inputs_needed\": \"..\", \"changes_for_people\": "
    "\"..\"} ] }."
)

# Phrases that betray a design which doesn't actually remove manual work — a non-solution.
_TIMID_MARKERS = (
    "completely inert", "remains inert", "does not record", "does not transcribe",
    "does not auto", "does nothing", "empty document", "no automation", "you still",
    "still type", "still manually", "manually type", "you just sign", "only assists",
    "merely a", "does not change", "static and inert", "purely a placeholder",
)


def is_timid(intervention):
    """True if a design doesn't meaningfully remove manual burden — it stays inert, only assists,
    or leaves the owner doing the work. These are the non-solutions the critique flagged."""
    t = (intervention.what_it_does + " " + intervention.changes_for_people).lower()
    return any(m in t for m in _TIMID_MARKERS)


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


def _memory_preamble(memory_text):
    if not memory_text:
        return ""
    return ("HOW YOU'VE SIZED UP THIS BUSINESS — let this shape HOW you design each "
            "intervention (how cautious, how much you keep the owner in control), never "
            "WHETHER you design one. Still design one per opportunity:\n" + memory_text + "\n\n")


async def design_interventions(client, model, opportunities, memory_text=""):
    """One intervention per opportunity, anchored to the opportunity's step. If the architect
    sat in on the interview, they design from what they understood about how this owner works
    (memory_text) — including what to keep them in control of.

    The Architect must never DROP an opportunity (rejecting is the skeptic's job). The local
    model sometimes ignores that and returns fewer, so we structurally re-prompt for any
    opportunity left undesigned until every one is covered or a bounded number of tries is up."""
    if not opportunities:
        return []
    map_text = serialize_map(model)
    designed = {}      # step_label -> Intervention
    pending = list(opportunities)
    for _ in range(3):
        if not pending:
            break
        user = (_memory_preamble(memory_text) + "WORKFLOW MAP:\n" + map_text
                + "\n\nOPPORTUNITIES (design one intervention for EACH — do not skip any):\n"
                + _serialize_opps(pending))
        result = await client.complete_json(ARCHITECT_SYSTEM, user, max_tokens=2048)
        for iv in _parse_interventions(result, {o.step_label for o in pending}):
            designed.setdefault(iv.step_label, iv)
        pending = [o for o in opportunities if o.step_label not in designed]
    # Preserve the Analyst's ordering, then force any TIMID design to be re-done boldly so the
    # Architect never ships a non-solution that leaves the owner doing the work.
    ordered = [designed[o.step_label] for o in opportunities if o.step_label in designed]
    return await _bolden_timid(client, map_text, ordered)


async def _bolden_timid(client, map_text, interventions, rounds=2):
    """Any intervention that doesn't actually remove manual burden gets re-designed to lift the
    drudgery (keeping the owner in control of judgment). Bounded; keeps the bolder result."""
    for _ in range(rounds):
        timid = [iv for iv in interventions if is_timid(iv)]
        if not timid:
            break
        user = ("WORKFLOW MAP:\n" + map_text + "\n\nTHESE DESIGNS ARE TOO TIMID — redesign each "
                "to actually remove the manual work on its step:\n"
                + "\n".join(f"- step '{iv.step_label}': was: {iv.what_it_does}" for iv in timid))
        result = await client.complete_json(BOLDEN_SYSTEM, user, max_tokens=2048)
        bolder = {iv.step_label: iv
                  for iv in _parse_interventions(result, {t.step_label for t in timid})}
        # Replace a timid design only if the redesign is no longer timid.
        interventions = [bolder[iv.step_label] if (iv.step_label in bolder
                         and not is_timid(bolder[iv.step_label])) else iv
                         for iv in interventions]
    return interventions


async def redesign_interventions(client, model, opportunities, objections, memory_text=""):
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
    if memory_text:
        user = ("WHAT YOU CAME TO UNDERSTAND SITTING IN ON THIS INTERVIEW (redesign around how "
                "this owner actually works):\n" + memory_text + "\n\n" + user)
    result = await client.complete_json(REDESIGN_SYSTEM, user, max_tokens=2048)
    return _parse_interventions(result, opp_steps)
