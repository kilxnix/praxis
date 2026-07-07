"""Phase 0 scoring. Automated structural checks are deterministic pass/fail;
the deeper quality dimensions are left for a human reviewer (Spec §7: no faked
quality oracle). gate_report aggregates against the Phase 0 pass criteria (Spec §8)."""
from praxis.models import WorkflowModel
from praxis.coverage import analyze_coverage

RUBRIC_FIELDS = ["adapted_to_them", "honest_about_gaps", "would_help"]
COVERAGE_BAR = 0.8


def structural_score(model_dict: dict) -> dict:
    model = WorkflowModel.from_dict(model_dict)
    rep = analyze_coverage(model)
    return {
        "connected": len(rep.orphan_steps) == 0,
        "grounded": len(rep.evidenceless) == 0,
        "grain_ok": len(rep.grain_outliers) == 0,
        "coverage": rep.overall,
        "orphans": len(rep.orphan_steps),
        "evidenceless": len(rep.evidenceless),
        "grain_outliers": len(rep.grain_outliers),
    }


def blank_scorecard(scenario_key: str) -> dict:
    return {
        "scenario_key": scenario_key,
        "auto": {},
        "human": {f: None for f in RUBRIC_FIELDS},  # reviewer fills 1-5
    }


def _auto_pass(auto: dict) -> bool:
    return bool(auto.get("connected") and auto.get("grounded")
               and auto.get("grain_ok") and auto.get("coverage", 0) >= COVERAGE_BAR)


def gate_report(scorecards: list) -> dict:
    n = len(scorecards)
    autos = [c.get("auto", {}) for c in scorecards]
    passes = [a for a in autos if _auto_pass(a)]
    secs = [a["seconds"] for a in autos if "seconds" in a]
    human_pending = sum(1 for c in scorecards
                        if any(c["human"][f] is None for f in RUBRIC_FIELDS))
    pass_rate = (len(passes) / n) if n else 0.0
    if pass_rate > 0.5:
        hint = "AUTO-PASS majority; awaiting human scores"
    elif pass_rate < 0.5:
        hint = "AUTO-FAIL — Discovery not reliable; change approach before building downstream"
    else:
        hint = "MIXED"
    return {
        "n": n,
        "auto_pass_rate": pass_rate,
        "avg_coverage": (sum(a.get("coverage", 0) for a in autos) / n) if n else 0.0,
        "avg_seconds": (sum(secs) / len(secs)) if secs else None,
        "human_pending": human_pending,
        "verdict_hint": hint,
    }
