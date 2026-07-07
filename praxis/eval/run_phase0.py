"""Phase 0 gate runner. Runs Discovery against every hard-client scenario on real
local Ollama, persists artifacts, and emits the gate report. This is the script whose
output decides whether we build the rest of the firm (Spec §8)."""
import asyncio
import json
import os
import time
from praxis.llm_client import OllamaClient
from praxis.eval.scenarios import SCENARIOS
from praxis.eval.harness import run_scenario, save_run
from praxis.eval.scoring import blank_scorecard, structural_score, gate_report


def _make_client():
    return OllamaClient()


def _make_sim_client():
    return OllamaClient()


async def main(out_dir="phase0_out", scenario_keys=None):
    os.makedirs(out_dir, exist_ok=True)
    scenarios = [s for s in SCENARIOS if (scenario_keys is None or s.key in scenario_keys)]
    interviewer = _make_client()
    sim = _make_sim_client()
    scorecards = []
    try:
        for sc in scenarios:
            result = await run_scenario(interviewer, sim, sc, clock=time.monotonic,
                                        max_turns=35, coverage_target=1.0)
            save_run(result, out_dir)
            card = blank_scorecard(sc.key)
            card["auto"] = structural_score(result.model_dict)
            card["auto"]["seconds"] = result.seconds
            card["auto"]["turns"] = result.turns
            scorecards.append(card)
    finally:
        await interviewer.close()
        await sim.close()

    report = gate_report(scorecards)
    with open(os.path.join(out_dir, "scorecards.json"), "w", encoding="utf-8") as f:
        json.dump(scorecards, f, indent=2)
    with open(os.path.join(out_dir, "gate_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    asyncio.run(main())
