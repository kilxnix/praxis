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
    "Return JSON {\"verdicts\": [ {\"step_label\": \"<exact step>\", \"verdict\": "
    "\"solid|weak|reject\", \"objection\": \"<one line; empty if solid>\"} ] }. Exactly one "
    "verdict per intervention."
)


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


async def review(client, interventions, assessments):
    if not interventions:
        return []
    result = await client.complete_json(SKEPTIC_SYSTEM,
                                        _serialize(interventions, assessments),
                                        max_tokens=2048)
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
