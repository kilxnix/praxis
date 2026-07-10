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
    "Then give the BUILDABLE spec — the fields the automation is compiled from. Be concrete and "
    "point at the owner's ACTUAL tools (the ones in the map), not invented ones:\n"
    "- trigger: the exact EVENT that starts it (e.g. 'a photo is taken of the work order', "
    "'the call ends', 'a new row lands in the sheet') — one clear event, not 'the user decides to'.\n"
    "- input_source: WHERE the input data comes from — name the real tool/artifact it reads "
    "(e.g. 'the phone camera photo', 'the QuickBooks invoice', 'the paper work order').\n"
    "- output_dest: WHERE the result goes — name the real tool/artifact it writes "
    "(e.g. 'the QuickBooks entry', 'a row in the master sheet', 'an SMS to the tech').\n"
    "- success_criteria: how you'd KNOW it worked on one real case — a checkable statement "
    "(e.g. 'the QuickBooks entry matches the parts and hours on the ticket, no field blank').\n\n"
    "Return JSON {\"interventions\": [ {\"step_label\": \"<exact step from the opportunity>\", "
    "\"what_it_does\": \"..\", \"where_it_plugs_in\": \"..\", \"inputs_needed\": \"..\", "
    "\"changes_for_people\": \"..\", \"trigger\": \"..\", \"input_source\": \"..\", "
    "\"output_dest\": \"..\", \"success_criteria\": \"..\"} ] }.\n"
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
    "For a CORE-WORK / creative opportunity (culling thousands of images, drafting a first "
    "contract, pre-diagnosing), design an 'AI FIRST PASS → HUMAN FINAL CALL' intervention: the "
    "AI does the heavy volume (pre-sorts, pre-drafts, shortlists) and the owner reviews and makes "
    "the final creative or professional decision. That lifts the volume off them WITHOUT taking "
    "away the judgment — do not design a timid 'it just watches' version, and do not refuse to "
    "automate the core just because it is skilled.\n"
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
    # The BUILDABLE spec SP2's Solutioner compiles into a BuildSpec IR. Defaults keep older
    # positional construction working; the Architect fills them in.
    trigger: str = ""            # the event that starts it
    input_source: str = ""       # where the input data comes from (a real tool/artifact)
    output_dest: str = ""        # where the result goes (a real tool/artifact)
    success_criteria: str = ""   # a checkable statement of "it worked" — SP2's Verifier gate

    def is_buildable(self):
        """True only when the spec carries what a compiler needs: a trigger, an I/O contract,
        and a way to verify correctness. Prose-only interventions are NOT buildable."""
        return all(f.strip() for f in
                   (self.trigger, self.input_source, self.output_dest, self.success_criteria))


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
    "For each, give what_it_does, where_it_plugs_in, inputs_needed, changes_for_people, plus the "
    "buildable spec: trigger, input_source, output_dest, success_criteria — specific to their "
    "real tools.\n\n"
    "Return JSON {\"interventions\": [ {\"step_label\": \"<exact step>\", \"what_it_does\": "
    "\"..\", \"where_it_plugs_in\": \"..\", \"inputs_needed\": \"..\", \"changes_for_people\": "
    "\"..\", \"trigger\": \"..\", \"input_source\": \"..\", \"output_dest\": \"..\", "
    "\"success_criteria\": \"..\"} ] }."
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
    "Also give the buildable spec: trigger (the event that starts it), input_source (the real "
    "tool/artifact the input comes from), output_dest (the real tool/artifact the result goes "
    "to), success_criteria (a checkable 'it worked' statement).\n\n"
    "Return JSON {\"interventions\": [ {\"step_label\": \"<exact step>\", \"what_it_does\": "
    "\"..\", \"where_it_plugs_in\": \"..\", \"inputs_needed\": \"..\", \"changes_for_people\": "
    "\"..\", \"trigger\": \"..\", \"input_source\": \"..\", \"output_dest\": \"..\", "
    "\"success_criteria\": \"..\"} ] }."
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
                trigger=_text(iv.get("trigger")),
                input_source=_text(iv.get("input_source")),
                output_dest=_text(iv.get("output_dest")),
                success_criteria=_text(iv.get("success_criteria")),
            ))
    return out


_DESIGN_BATCH = 3   # interventions per LLM call — small enough that the 9-field JSON never truncates


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
    # Design in small BATCHES. Each intervention now carries the full buildable spec (9 fields),
    # so asking for many at once truncates the JSON at the token limit and silently yields ZERO.
    # Batching keeps every response within budget; the outer loop re-prompts for any still missing.
    for _ in range(3):
        pending = [o for o in opportunities if o.step_label not in designed]
        if not pending:
            break
        for i in range(0, len(pending), _DESIGN_BATCH):
            batch = pending[i:i + _DESIGN_BATCH]
            user = (_memory_preamble(memory_text) + "WORKFLOW MAP:\n" + map_text
                    + "\n\nOPPORTUNITIES (design one intervention for EACH — do not skip any):\n"
                    + _serialize_opps(batch))
            result = await client.complete_json(ARCHITECT_SYSTEM, user, max_tokens=3000)
            for iv in _parse_interventions(result, {o.step_label for o in batch}):
                designed.setdefault(iv.step_label, iv)
    # Preserve the Analyst's ordering, then force any TIMID design to be re-done boldly so the
    # Architect never ships a non-solution that leaves the owner doing the work.
    ordered = [designed[o.step_label] for o in opportunities if o.step_label in designed]
    return await _bolden_timid(client, map_text, ordered)


def fallback_interventions(opportunities):
    """Owned backstop: if the Architect returns nothing on real opportunities (a stochastic/
    truncation failure, not a truth), build a bare intervention per opportunity from the
    opportunity's own description so the plan is never silently empty. Not buildable (no spec) —
    it will show as a recommendation but be marked not-yet-buildable in the SP2 handoff."""
    return [Intervention(o.step_label,
                         f"AI does the heavy work of '{o.step_label}' — {o.description}",
                         "the step where this happens", "the data this step already uses",
                         "less manual work; you keep the final call")
            for o in opportunities]


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
