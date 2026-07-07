"""The Skeptic: the firm's internal quality gate. Pressure-tests each proposed intervention
— is it grounded in what the client actually said, will it genuinely help, and does it force
the business to fit the tool (an Ocean-Principle violation)? Emits a verdict per intervention;
the Principal drops rejects and carries unresolved objections into the deliverable as caveats."""
from dataclasses import dataclass

VERDICTS = {"solid", "weak", "reject"}

SKEPTIC_SYSTEM = (
    "You are a fair but sharp skeptic reviewing proposed AI CHANGES for a small business. "
    "Each item is a change AI would MAKE to a step they do manually today — judge the CHANGE "
    "(what the AI would do), not the current manual step. Give a verdict for EVERY item.\n\n"
    "- solid: grounded in a real task they do, genuinely helpful, fits how they work.\n"
    "- weak: a real, nameable concern (creates new work or risk, or overreaches past the task).\n"
    "- reject: would make things worse, isn't grounded, overrides a step they clearly value "
    "doing themselves, or invents a workflow they never mentioned.\n\n"
    "Do NOT reject something for being manual or not fully automated — a manual step is fine if "
    "it fits. Base each objection on the specific intervention and workflow in front of you, "
    "not on generic beliefs about small businesses.\n\n"
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
