"""The Skeptic: the firm's internal quality gate. Pressure-tests each proposed intervention
— is it grounded in what the client actually said, will it genuinely help, and does it force
the business to fit the tool (an Ocean-Principle violation)? Emits a verdict per intervention;
the Principal drops rejects and carries unresolved objections into the deliverable as caveats."""
from dataclasses import dataclass
from praxis.discovery_signals import canonical_label

VERDICTS = {"solid", "weak", "reject"}

SKEPTIC_SYSTEM = (
    "You are the skeptic on an AI-implementation team for a small business. Your ONE job is to "
    "protect the owner from changes that overreach or don't fit how they actually work. You are "
    "NOT here to push for more automation — a smaller, more cautious change is the SAFER, BETTER "
    "answer, never a weakness. Each item is a change AI would MAKE to a step they do manually "
    "today; judge the CHANGE, not the manual step. Give one verdict for EVERY item.\n\n"
    "These are NOT reasons to reject or flag — a design with any of these is doing the RIGHT "
    "thing:\n"
    "- it keeps a human in the loop or leaves the owner in control of a step\n"
    "- it is manual, partial, or 'only' assists instead of fully automating\n"
    "- it 'doesn't go far enough', 'misses a chance to automate more', or 'could do more'\n"
    "- it is small, modest, or cautious\n"
    "- it proposes a tool, app, or AI capability the owner never named (OCR, a reminder, a "
    "transcript, a photo lookup). Proposing a solution they hadn't thought of IS your team's "
    "job — the owner only has to have described the PAIN or STEP, not the fix.\n"
    "- it removes manual drudgery the owner COMPLAINED about (re-typing, transcribing, copying "
    "between tools). Lifting busywork they resent is the whole point — do not defend the "
    "friction. Only their JUDGMENT and the decisions they value are protected, not their "
    "data-entry chores.\n"
    "NEVER reject or weaken an item for being too conservative, or for naming a tool the owner "
    "didn't. Wanting more automation is the opposite of your job.\n\n"
    "- solid: grounded in something they actually said, genuinely helpful, and fits how they "
    "work. Cautious-but-useful is SOLID.\n"
    "- weak: a real, specific risk the CHANGE itself introduces (it could fail silently, create "
    "new work, or act on bad data) — name it concretely.\n"
    "- reject: the PAIN or step it targets isn't grounded in what they said, it invents a NEED "
    "or problem they don't actually have (or assumes a fact about their business that isn't "
    "true), it forces them to change how they work, it takes over a step they clearly value "
    "doing themselves, or it would plainly make things worse. (Proposing an unnamed TOOL for a "
    "real pain is fine — see above; only inventing a fake NEED is a reject.)\n\n"
    "Base every objection on the specific intervention and workflow in front of you, not on "
    "generic beliefs about small businesses or about automation.\n\n"
    "CRITICAL — do NOT invent an owner preference. Your understanding of the business is YOUR "
    "read, not the owner's stated words. You may NOT reject or weaken a change by claiming the "
    "owner 'values control', 'wants a human in the loop', 'prefers to keep it manual', or "
    "'requires final authority' UNLESS the owner ACTUALLY SAID SO. A person doing a step by hand "
    "today is describing their CURRENT process, not stating they want to keep doing it by hand. "
    "Automating manual data entry they complained about is NOT 'forcing them to change how they "
    "work' — it is the job. Reject only for a CONCRETE risk the change introduces (it could fail, "
    "error, act on bad data, break something) or for a need it plainly invents — never for a "
    "preference you attribute to them without evidence.\n\n"
    "Return JSON {\"verdicts\": [ {\"step_label\": \"<exact step>\", \"verdict\": "
    "\"solid|weak|reject\", \"objection\": \"<one line; empty if solid>\"} ] }. Exactly one "
    "verdict per intervention."
)

# Owned guard against the recurring failure where the skeptic INVENTS an owner preference
# ("they value human-in-the-loop control") and rejects the biggest opportunity on it. A
# preference-framed objection cites what the owner supposedly wants; a risk-framed one names a
# concrete way the change fails. We can tell them apart by their words.
_PREFERENCE_MARKERS = (
    "value", "prefer", "wants to keep", "want to keep", "human-in-the-loop", "human in the loop",
    "in control", "final authority", "surrender", "strict gate", "how they work", "control of",
    "their authority", "keep them in control", "removes control", "removing control",
    "manual verification", "manual authority", "wants control", "likes doing", "values doing",
    # "the owner's hard gate / boundary / requirement for X" framings — a stated rule the owner
    # supposedly imposes, not a concrete failure of the change. Killed the photographer's culling.
    "hard gate", "gate requiring", "gate that", "their gate", "boundary", "temporal separation",
    "strict separation", "sacred", "sacrosanct", "mandate", "insists on", "requires strict",
)
_RISK_MARKERS = (
    "fail", "error", "wrong", "break", "lose", "loses", "losing", "miss", "risk of", "inaccurate",
    "corrupt", "silently", "hallucin", "mistake", "unreliable", "duplicate", "double-bill",
    "bad data", "incomplete", "delay",
)


# "This invents a need the owner doesn't have" — a valid rejection for an UNGROUNDED idea, but
# an INVALID one for a step whose burden is measured-high and grounding recurring: the need is
# real, the skeptic is just resisting automating the core. Killed the photographer's culling.
_INVENTED_NEED_MARKERS = (
    "invents a need", "invent a need", "invented need", "manufactures a need", "no real need",
    "unnecessary", "artificial need", "creates a need", "not needed", "no genuine need",
)


def _is_preference_objection(objection):
    o = (objection or "").lower()
    return any(m in o for m in _PREFERENCE_MARKERS) and not any(r in o for r in _RISK_MARKERS)


def _is_invented_need_objection(objection):
    o = (objection or "").lower()
    return any(m in o for m in _INVENTED_NEED_MARKERS) and not any(r in o for r in _RISK_MARKERS)


def ground_verdicts(verdicts, model):
    """For a HIGH-burden step (measured drudgery the owner clearly wants gone), a reject/weak that
    rests on an invented PREFERENCE rather than a concrete risk is not valid — flip it to solid.
    This is the owned counterweight to the skeptic fabricating 'they value control' and killing
    the top opportunity, which also contradicted the recommendations."""
    from praxis.grounding import measure_burden, burden_severity
    out = []
    for v in verdicts:
        invalid = _is_preference_objection(v.objection) or _is_invented_need_objection(v.objection)
        if (v.verdict in ("reject", "weak") and invalid
                and burden_severity(measure_burden(v.step_label, model)) == "high"):
            out.append(Verdict(v.step_label, "solid", ""))
        else:
            out.append(v)
    return out


@dataclass
class Verdict:
    step_label: str
    verdict: str
    objection: str


def _serialize(interventions, assessments):
    lines = []
    for iv in interventions:
        # Frame it as the PROPOSED CHANGE (what the AI does), so the Skeptic evaluates the
        # change and doesn't mistake it for the current manual step.
        lines.append(f"- On the step they now do by hand ('{iv.step_label}'), the proposed AI "
                     f"change is: {iv.what_it_does}")
    return "\n".join(lines)


async def review(client, interventions, assessments, memory_text=""):
    if not interventions:
        return []
    user = _serialize(interventions, assessments)
    if memory_text:
        user = ("YOUR OWN READ OF THIS BUSINESS (this is the FIRM's understanding, NOT the "
                "owner's stated words — do not cite it as a preference the owner expressed):\n"
                + memory_text + "\n\nPROPOSED CHANGES:\n" + user)
    result = await client.complete_json(SKEPTIC_SYSTEM, user, max_tokens=2048)
    raw = result.get("verdicts", []) if isinstance(result, dict) else []
    # Match each returned verdict to a real intervention by CANONICAL label (absorbs case,
    # punctuation, and article differences). Exact string-matching here silently dropped every
    # verdict when the model echoed the label even slightly differently — bypassing the gate.
    by_canon = {canonical_label(iv.step_label): iv.step_label for iv in interventions}
    out, matched, leftover = [], set(), []
    for v in raw:
        if not isinstance(v, dict):
            continue
        verdict = (v.get("verdict") or "").strip().lower()
        verdict = verdict if verdict in VERDICTS else "weak"
        objection = (v.get("objection") or "").strip()
        real = by_canon.get(canonical_label(v.get("step_label") or ""))
        if real and real not in matched:
            out.append(Verdict(real, verdict, objection))
            matched.add(real)
        else:
            leftover.append((verdict, objection))
    # Rescue verdicts whose label didn't canonically match: the Skeptic returns exactly one
    # verdict per intervention in order, so pair leftovers to still-unmatched interventions.
    unmatched = [iv.step_label for iv in interventions if iv.step_label not in matched]
    for (verdict, objection), label in zip(leftover, unmatched):
        out.append(Verdict(label, verdict, objection))
    return out


def signed_off(verdicts):
    """True if the firm has at least one solid intervention to ship."""
    return any(v.verdict == "solid" for v in verdicts)
