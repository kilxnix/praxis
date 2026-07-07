"""The Business-case agent: scores and prioritizes the Architect's interventions on
effort, time saved, risk, and disruption, and tags each with a priority tier. Scores are
rough, honest estimates (a local model can't produce precise ROI) — the value is relative
ranking so the rollout can lead with quick wins. Scores only; does not design or build."""
from dataclasses import dataclass

LEVELS = {"low", "medium", "high"}
PRIORITIES = {"quick win", "worth it", "big bet", "skip"}

BUSINESS_SYSTEM = (
    "You are a pragmatic business analyst for a small business. You are given AI "
    "interventions already designed for their workflow. Score each one honestly. These are "
    "rough estimates, not precise ROI — the point is relative ranking.\n\n"
    "For each intervention rate (low/medium/high):\n"
    "- effort: how hard it is for them to adopt\n"
    "- time_saved: how much manual time/effort it removes\n"
    "- risk: chance it breaks something or needs babysitting\n"
    "- disruption: how much it changes their current way of working\n\n"
    "Then assign a priority: 'quick win' (low effort + real time saved), 'worth it', "
    "'big bet' (high effort but high payoff), or 'skip' (not worth it). Add a one-line "
    "rationale.\n\n"
    "Return JSON {\"assessments\": [ {\"step_label\": \"<exact step>\", \"effort\": \"..\", "
    "\"time_saved\": \"..\", \"risk\": \"..\", \"disruption\": \"..\", \"priority\": \"..\", "
    "\"rationale\": \"..\"} ] }."
)


@dataclass
class Assessment:
    step_label: str
    effort: str
    time_saved: str
    risk: str
    disruption: str
    priority: str
    rationale: str


def _serialize_interventions(interventions):
    return "\n".join(
        f"- step '{iv.step_label}': {iv.what_it_does} (plugs into {iv.where_it_plugs_in})"
        for iv in interventions
    )


def _lvl(v):
    v = (v or "").strip().lower()
    return v if v in LEVELS else "medium"


def derive_priority(effort, time_saved, risk):
    """Priority is DERIVED from the scores so it can never contradict the effort/reward math
    (e.g. high effort for medium reward can't be sold as a casual 'quick win' or 'worth it')."""
    if time_saved == "low" and effort != "low":
        return "skip"          # costs real effort, saves little
    if effort == "high":
        return "big bet"       # high effort is always a bet, never a quick win
    if effort == "low" and time_saved == "high" and risk != "high":
        return "quick win"
    return "worth it"


async def score_interventions(client, interventions):
    if not interventions:
        return []
    iv_steps = {iv.step_label for iv in interventions}
    result = await client.complete_json(BUSINESS_SYSTEM,
                                        _serialize_interventions(interventions),
                                        max_tokens=2048)
    out = []
    for a in (result.get("assessments", []) if isinstance(result, dict) else []):
        if not isinstance(a, dict):
            continue
        label = a.get("step_label")
        if label not in iv_steps:
            continue
        effort, saved, risk = _lvl(a.get("effort")), _lvl(a.get("time_saved")), _lvl(a.get("risk"))
        out.append(Assessment(
            label, effort, saved, risk, _lvl(a.get("disruption")),
            derive_priority(effort, saved, risk),   # deterministic, consistent with the scores
            (a.get("rationale") or "").strip(),
        ))
    return out


_PRIORITY_ORDER = {"quick win": 0, "worth it": 1, "big bet": 2, "skip": 3}


def prioritized(assessments):
    """Assessments ordered for the rollout: quick wins first, skips last."""
    return sorted(assessments, key=lambda a: _PRIORITY_ORDER.get(a.priority, 1))
