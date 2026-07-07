"""The Skeptic: the firm's internal quality gate. Pressure-tests each proposed intervention
— is it grounded in what the client actually said, will it genuinely help, and does it force
the business to fit the tool (an Ocean-Principle violation)? Emits a verdict per intervention;
the Principal drops rejects and carries unresolved objections into the deliverable as caveats."""
from dataclasses import dataclass

VERDICTS = {"solid", "weak", "reject"}

SKEPTIC_SYSTEM = (
    "You are a hard-nosed but fair skeptic reviewing proposed AI interventions for a small "
    "business. Judge ONLY from evidence — what the owner actually said and does. For each "
    "intervention:\n"
    "1. Grounded — does it address a real pain the owner mentioned, not an assumption?\n"
    "2. Will it help — does it remove real effort without creating new problems or risk?\n"
    "3. Respects the owner — does it override something they said they VALUE doing themselves "
    "(e.g. personally writing proposals)? If so, that's a reject.\n"
    "4. Right-sized — does it invent adjacent features/workflows they never asked about? If so, "
    "flag it.\n\n"
    "Do NOT reject something just because it isn't fully automated. A small manual trigger or "
    "keeping a step by hand is perfectly fine if it fits how they work — automation is not a "
    "virtue in itself. Reject on evidence, never on ideology.\n\n"
    "Verdict: 'solid' (grounded, helpful, respectful, right-sized), 'weak' (a genuine concern "
    "you can't wave away), or 'reject' (fails one badly). One-line objection for weak/reject, "
    "empty for solid. Ground the objection in what they SAID.\n\n"
    "Return JSON {\"verdicts\": [ {\"step_label\": \"<exact step>\", \"verdict\": "
    "\"solid|weak|reject\", \"objection\": \"..\"} ] }."
)


@dataclass
class Verdict:
    step_label: str
    verdict: str
    objection: str


def _serialize(interventions, assessments):
    by_step = {a.step_label: a for a in assessments}
    lines = []
    for iv in interventions:
        a = by_step.get(iv.step_label)
        pr = f" [{a.priority}]" if a else ""
        lines.append(f"- step '{iv.step_label}'{pr}: {iv.what_it_does} "
                     f"(needs {iv.inputs_needed})")
    return "\n".join(lines)


async def review(client, interventions, assessments):
    if not interventions:
        return []
    iv_steps = {iv.step_label for iv in interventions}
    result = await client.complete_json(SKEPTIC_SYSTEM,
                                        _serialize(interventions, assessments),
                                        max_tokens=2048)
    out = []
    for v in (result.get("verdicts", []) if isinstance(result, dict) else []):
        if not isinstance(v, dict):
            continue
        label = v.get("step_label")
        if label not in iv_steps:
            continue
        verdict = (v.get("verdict") or "").strip().lower()
        out.append(Verdict(label, verdict if verdict in VERDICTS else "weak",
                           (v.get("objection") or "").strip()))
    return out


def signed_off(verdicts):
    """True if the firm has at least one solid intervention to ship."""
    return any(v.verdict == "solid" for v in verdicts)
