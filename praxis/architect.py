"""The Architect: designs a concrete AI intervention for each opportunity the Analyst
found. Specific to the client's own tools and steps (Ocean-safe). It designs only — it does
not score/prioritize (Business-case) or build the automation (SP2, the Build Wing).

When the local model can't ship a full design for high-burden core work (culling thousands of
photos, first-draft contracts, etc.), an owned deterministic pattern fills in a buildable
AI-first-pass → human-final-call intervention so the opportunity never degrades to "needs
scoping" on the plan.
"""
import re
from dataclasses import dataclass
from praxis.analyst import serialize_map
from praxis.models import NodeType, EdgeType

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
    "contract, SKETCHING CONCEPTS, making Illustrator edits, generating artwork), design an "
    "'AI FIRST PASS → HUMAN FINAL CALL' intervention: the AI does the heavy volume (pre-sorts, "
    "pre-drafts, shortlists, concept options, first-pass edits) and the owner reviews and makes "
    "the final creative or professional decision. It must ACTIVELY DO the work, not passively "
    "watch. Concrete example for 'cull 3000 photos': the AI scores every image (sharp, eyes "
    "open, composition, near-duplicates), auto-rejects the obvious throwaways, and hands her a "
    "ranked shortlist of ~the best candidates to approve — she makes the final keeper call but "
    "never scrolls all 3000. For 'draft a contract': the AI produces a complete first draft from "
    "the intake details; the lawyer edits and approves. For 'sketch concepts' / 'generate "
    "artwork': the AI produces 3–5 concept variations from the brief and brand assets as review "
    "boards the designer can refine (on paper or in their tool — their choice); they never start "
    "from a blank page. For 'make changes in Illustrator': the AI applies the routine marked-up "
    "edits first; the designer reviews and finishes. NEVER design a 'silent observer', a "
    "'remains dormant', a 'non-destructive monitor', or an 'it just flags' version — that is the "
    "timid non-solution that fails. Do the heavy lifting; leave the judgment.\n"
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
    # passive "it watches / flags but doesn't act" designs — the timid non-solution for core work
    "silent observer", "silent, background", "background observer", "non-destructive",
    "it just flags", "only flags", "merely flags", "passively monitor", "just watches",
    "does not delete", "does not select",
    # "passive safety net / does not replace culling" — the videographer failure mode: design
    # DISCLAIMS doing the volume work and leaves the owner grinding through every item.
    "safety net", "does not replace", "does not automate", "does not cull",
    "does not score", "does not pre-sort", "does not presort", "does not shortlist",
    "only runs if", "only if the owner", "if the owner explicitly", "if you explicitly ask",
    "after their manual", "after you finish manually", "after your manual",
    "optional helper", "does not remove", "still go through every", "still review every",
    "still review all", "leaves you to review every", "you still scroll",
    "does not do the heavy", "does not do the volume", "simply organizes",
    "only organizes", "organizes those specific files",
    "passive 'safety", 'passive "safety', "passive safety",
    # designer failure: "Remains dormant / performs NO drafting / zero extraction" — the model
    # disclaims the work entirely rather than designing a first-pass for creative core.
    "remains dormant", "remaining dormant", "completely dormant", "stays dormant",
    "performs no ", "performs zero", "does not draft", "does not parse", "does not scan",
    "does not generate", "does not create", "does not edit", "does not apply",
    "does not draw", "does not sketch", "zero data extraction", "no drafting",
    "but does not draft", "but does not", "does not send anything", "functionally useless",
    "offers no utility", "ignores a step", "passively monitors", "passive monitoring",
    "waits for a manual", "waits for the 'approved'", "only the file export",
)

# Regex disclaimers: "does not <verb the work>" even when the exact phrase isn't listed above.
_TIMID_DISCLAIM = re.compile(
    r"does not (replace|automate|cull|select|score|pre-?sort|shortlist|remove|do the|"
    r"lift|handle the volume|touch the|draft|parse|scan|generate|create|edit|draw|"
    r"sketch|apply|produce|design)",
    re.I,
)
_TIMID_PASSIVE = re.compile(
    r"\bpassive\b.{0,40}\b(net|monitor|observer|helper|safety|background|vault)\b|"
    r"\b(net|monitor|observer|helper|safety|vault)\b.{0,40}\bpassive\b",
    re.I,
)
def is_timid(intervention):
    """True if a design doesn't meaningfully remove manual burden — it stays inert/dormant,
    only assists, disclaims doing the work, or leaves the owner doing the grind."""
    t = (intervention.what_it_does + " " + intervention.changes_for_people).lower()
    if any(m in t for m in _TIMID_MARKERS):
        return True
    if _TIMID_DISCLAIM.search(t) or _TIMID_PASSIVE.search(t):
        return True
    # "Remains dormant. It does not X" — full disclaimer of the opportunity
    if "dormant" in t or ("remains" in t and "does not" in t):
        return True
    return False


def _step_io(model, step_label):
    """The tools / inputs / outputs the owner already named for this step — Ocean anchors."""
    tools, inputs, outputs = [], [], []
    if model is None:
        return tools, inputs, outputs
    for n in model.nodes_of(NodeType.STEP):
        if n.label != step_label:
            continue
        for e in model.edges_from(n.id):
            if e.target not in model.nodes:
                continue
            label = model.nodes[e.target].label
            if e.type == EdgeType.USES:
                tools.append(label)
            elif e.type == EdgeType.CONSUMES:
                inputs.append(label)
            elif e.type == EdgeType.PRODUCES:
                outputs.append(label)
        break
    return tools, inputs, outputs


def _core_kind(opportunity):
    """Form-level pattern for the volume layer — never a business template. Driven by the
    opportunity's own words (step, capability, description), not a canned industry list."""
    blob = " ".join([
        opportunity.step_label or "",
        opportunity.capability or "",
        opportunity.description or "",
        opportunity.evidence or "",
    ]).lower()
    # Pure creative generation FIRST — sketch / artwork / Illustrator — before generic "image"
    # cull, so "sketch concepts" and "make changes in Illustrator" don't mis-route to culling.
    if any(k in blob for k in (
            "sketch", "artwork", "illustrator", "concept variation", "concept options",
            "generate first-draft creative", "first-draft creative", "creative work",
            "logo option", "layout option", "design variation", "make changes in",
            "edit the design", "draw ", "paint ", "comp ", "mockup", "wireframe",
            "generate multiple", "rough concept", "visual concept")):
        return "create"
    if any(k in blob for k in (
            "cull", "photo", "image", "lightroom", "raw file", "gallery", "select keeper",
            "sort image", "thousands of image", "thousands of photo", "pick best shot")):
        return "cull"
    if any(k in blob for k in (
            "draft", "contract", "proposal", "will ", "estate", "write first", "first draft",
            "document template", "clarifying question", "quote")):
        return "draft"
    if any(k in blob for k in (
            "diagnos", "inspect", "troubleshoot", "fault", "model plate", "pre-screen")):
        return "diagnose"
    if any(k in blob for k in (
            "transcri", "call recording", "phone call", "meeting note", "voice note",
            "spoken note")):
        return "transcribe"
    if any(k in blob for k in (
            "invoice", "quickbooks", "re-type", "retype", "re-key", "rekey", "copy into",
            "spreadsheet", "data entry", "type into")):
        return "data_entry"
    if any(k in blob for k in (
            "first pass", "pre-sort", "pre-select", "high-volume", "high volume",
            "thousands", "hundreds", "volume")):
        return "volume"
    return "volume"


def owned_core_design(opportunity, model=None):
    """Deterministic, shippable AI-first-pass design for high-burden core work.

    Used when the local model returns a timid, empty, or prose-only intervention for the work
    that costs the owner the most. Always buildable (full trigger/I/O/success-criteria) and
    never timid: the AI does the volume; the owner keeps the final judgment. Anchors to the
    owner's named tools when the map has them.
    """
    step = opportunity.step_label
    tools, inputs, outputs = _step_io(model, step)
    tool = tools[0] if tools else f"the tools you already use for '{step}'"
    inp = inputs[0] if inputs else f"the full set of work items for '{step}'"
    out = outputs[0] if outputs else f"a ranked shortlist ready for your final call on '{step}'"
    kind = _core_kind(opportunity)

    if kind == "create":
        # Pure creative generation: concepts, Illustrator edits, artwork first-pass.
        # Ocean-safe: options feed THEIR process (paper or digital); final craft stays theirs.
        # Shippable success criteria = options exist that apply the brief/brand — not "looks good".
        what = (
            f"When '{step}' starts, AI produces 3–5 first-pass concept variations from the brief, "
            f"brand assets, and constraints already on hand — as review boards you can open in "
            f"{tool} or print to sketch over. For revision work, it applies the routine marked-up "
            f"edits first (swap approved assets, type/color notes, simple layout moves) as a "
            f"first-pass layer. You pick, refine, and finish — you never start from a blank page. "
            f"Final creative judgment stays yours."
        )
        where = f"feeds '{step}' (your sketching or {tool} — you choose how to refine)"
        needed = (
            f"the brief/constraints and brand assets for '{step}'; optional write access to {tool}"
        )
        changes = (
            "you choose among first-pass concepts (or review first-pass edits) instead of "
            "starting from nothing; every final creative call remains yours"
        )
        trigger = f"brief, brand assets, and constraints are ready for '{step}'"
        input_source = inputs[0] if inputs else f"brief, brand assets, and constraints for '{step}'"
        output_dest = (
            out if outputs
            else f"3–5 concept boards / first-pass files ready for '{step}' (in {tool} or printable)"
        )
        success = (
            "at least 3 concept options (or a first-pass edit layer) exist that apply the stated "
            "brief constraints and brand assets; you only select, refine, and approve"
        )
    elif kind == "cull":
        what = (
            f"An AI first-pass scores every item for '{step}' (sharpness, eyes open, composition, "
            f"near-duplicates) in {tool}, auto-rejects obvious throwaways, and hands you a ranked "
            f"shortlist of the best candidates. You make the final keeper call — you never scroll "
            f"the full volume."
        )
        where = f"{tool} at the '{step}' stage"
        needed = f"read access to {inp}; write access to a shortlist/collection in {tool}"
        changes = (
            "you review and approve a ranked shortlist instead of inspecting every item by hand; "
            "final creative call stays yours"
        )
        trigger = f"a new batch is ready for '{step}'"
        input_source = inp
        output_dest = out if outputs else f"ranked shortlist collection in {tool}"
        success = (
            f"obvious throwaways are auto-rejected; the shortlist is a small fraction of the full "
            f"set; you only review the shortlist and keep final say"
        )
    elif kind == "draft":
        what = (
            f"When '{step}' starts, AI produces a complete first draft from the intake details "
            f"already on hand, written into {tool}. You edit and approve — you never start from a "
            f"blank page."
        )
        where = f"{tool} during '{step}'"
        needed = f"the intake details that feed '{step}'; write access to {tool}"
        changes = "you refine and approve a full first draft instead of drafting from scratch"
        trigger = f"intake details for a job are ready and '{step}' begins"
        input_source = inputs[0] if inputs else f"intake notes and facts for '{step}'"
        output_dest = out if outputs else f"first draft document in {tool}"
        success = (
            f"a complete draft exists in {tool} with the intake facts filled in; you only edit "
            f"and approve"
        )
    elif kind == "diagnose":
        what = (
            f"When work hits '{step}', AI pre-reads the photos, model info, and notes, then "
            f"produces a ranked shortlist of likely causes and next checks in {tool}. You confirm "
            f"the diagnosis — the heavy pre-screen is done for you."
        )
        where = f"{tool} at '{step}'"
        needed = f"photos/notes entering '{step}'; write access to {tool}"
        changes = "you confirm or override a pre-screened shortlist instead of starting cold"
        trigger = f"new job materials arrive for '{step}'"
        input_source = inputs[0] if inputs else f"photos and notes for '{step}'"
        output_dest = out if outputs else f"ranked diagnosis shortlist in {tool}"
        success = (
            "a ranked shortlist of likely causes is ready before you decide; final diagnosis "
            "stays yours"
        )
    elif kind == "transcribe":
        what = (
            f"When a call or spoken note for '{step}' ends, AI transcribes and structures it into "
            f"{tool} automatically. You review and correct — you never re-type from memory."
        )
        where = f"{tool} after '{step}'"
        needed = f"audio or spoken notes for '{step}'; write access to {tool}"
        changes = "you review a structured transcript instead of typing notes by hand"
        trigger = f"a recording or spoken note for '{step}' is available"
        input_source = inputs[0] if inputs else f"call recording or voice note for '{step}'"
        output_dest = out if outputs else f"structured notes in {tool}"
        success = (
            f"structured notes land in {tool} without manual typing; you only correct mistakes"
        )
    elif kind == "data_entry":
        what = (
            f"When '{step}' is ready, AI reads the source (ticket, form, photo) and enters every "
            f"field into {tool} for you. You glance and confirm — no re-typing."
        )
        where = f"{tool} during '{step}'"
        needed = f"the source artifact for '{step}'; write access to {tool}"
        changes = "you confirm auto-entered fields instead of typing them"
        trigger = f"a completed source for '{step}' is available"
        input_source = inputs[0] if inputs else f"source ticket/form/photo for '{step}'"
        output_dest = out if outputs else f"completed entry in {tool}"
        success = (
            f"every field lands in {tool} matching the source; no blank required field; you only "
            f"confirm"
        )
    else:  # volume / generic high-burden first pass
        what = (
            f"AI does the heavy first pass on '{step}' — pre-sorts, pre-fills, or generates the "
            f"volume work in {tool} — and hands you a shortlist or draft to approve. You keep the "
            f"final judgment; you never grind through the full volume by hand."
        )
        where = f"{tool} at '{step}'"
        needed = f"the inputs already used for '{step}'; write access to {tool}"
        changes = (
            "you review AI's first-pass output and make the final call instead of doing the full "
            "volume yourself"
        )
        trigger = f"work is ready for '{step}'"
        input_source = inp
        output_dest = out
        success = (
            f"first-pass output exists for every item in the batch; you only review and decide"
        )

    # Fold the opportunity's own description so the rec stays specific to THIS pain.
    desc = (opportunity.description or "").strip()
    if desc and desc.lower() not in what.lower():
        what = f"{what} ({desc})"

    return Intervention(
        step, what, where, needed, changes,
        trigger=trigger, input_source=input_source,
        output_dest=output_dest, success_criteria=success,
    )


def _is_high_core(opportunity, model):
    """High-severity (analyst) or measured high-burden (owner's words) — the work that must
    never degrade to 'needs scoping'."""
    if getattr(opportunity, "severity", "") == "high":
        return True
    if model is None:
        return False
    from praxis.grounding import measure_burden, burden_severity
    return burden_severity(measure_burden(opportunity.step_label, model)) == "high"


def needs_owned_design(intervention, opportunity, model=None):
    """True when the design is missing entirely, or is a timid non-solution on high-burden core
    work. Non-timid prose that only lacks SP2 fields is completed, not replaced (see
    complete_buildable_spec)."""
    if intervention is None:
        return True
    return is_timid(intervention) and _is_high_core(opportunity, model)


def complete_buildable_spec(intervention, opportunity, model=None):
    """Fill missing trigger/I/O/success-criteria from the owned core pattern without throwing
    away a solid what_it_does the model already produced."""
    if intervention is None or intervention.is_buildable():
        return intervention
    owned = owned_core_design(opportunity, model)
    return Intervention(
        intervention.step_label,
        intervention.what_it_does,
        intervention.where_it_plugs_in or owned.where_it_plugs_in,
        intervention.inputs_needed or owned.inputs_needed,
        intervention.changes_for_people or owned.changes_for_people,
        trigger=intervention.trigger or owned.trigger,
        input_source=intervention.input_source or owned.input_source,
        output_dest=intervention.output_dest or owned.output_dest,
        success_criteria=intervention.success_criteria or owned.success_criteria,
    )


def ensure_shippable_designs(interventions, opportunities, model=None):
    """Guarantee every high-burden opportunity has a shippable design:
    - missing or timid on high-burden core → full owned AI-first-pass design
    - solid prose missing SP2 fields → complete the buildable spec in place
    - anything else left as the architect wrote it
    Also fills any opportunity the architect skipped entirely. Preserves Analyst ordering."""
    by_label = {iv.step_label: iv for iv in interventions}
    out = []
    for o in opportunities:
        iv = by_label.get(o.step_label)
        if iv is None or needs_owned_design(iv, o, model):
            out.append(owned_core_design(o, model))
        elif _is_high_core(o, model) and not iv.is_buildable():
            out.append(complete_buildable_spec(iv, o, model))
        else:
            out.append(iv)
    return out


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
    ordered = await _bolden_timid(client, map_text, ordered)
    # Last structural backstop: high-burden core work that is still timid or missing a buildable
    # spec gets an owned AI-first-pass design (specific tool pattern + full SP2 fields). The local
    # model often finds culling but can't ship a design for it — this is what closes that gap.
    return ensure_shippable_designs(ordered, opportunities, model)


def fallback_interventions(opportunities, model=None):
    """Owned backstop: if the Architect returns nothing on real opportunities (a stochastic/
    truncation failure, not a truth), build a full shippable intervention per opportunity so the
    plan is never silently empty. Uses the same AI-first-pass core patterns as ensure_shippable
    so fallbacks are buildable and never degrade to 'needs scoping'."""
    return [owned_core_design(o, model) for o in opportunities]


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
