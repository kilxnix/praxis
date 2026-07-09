"""Learning-payoff proof: does the same firm get BETTER over engagements?

Blank minds -> HVAC x2 (baseline) -> 4 different businesses (accumulate + consolidate
lessons) -> HVAC x2 again (seasoned). Same business at both ends, so the delta is the
learning, not the scenario. Deterministic scorecard per job; minds dumped at the end.
"""
import asyncio
import os
import shutil
import sys
import time

sys.path.insert(0, os.getcwd())     # run from the repo root: python gate_val/learning_proof.py

from praxis.llm_client import OllamaClient
from praxis.eval.scenarios import SCENARIOS
from praxis.pipeline import run_pipeline, save_engagement
from praxis.models import WorkflowModel, NodeType
from praxis.grounding import measure_burden
from praxis.architect import is_timid
from praxis.firm_agent import AgentMind, ROSTER

JOBS = ["hvac_tech", "hvac_tech",                                  # blank baseline x2
        "solo_lawyer", "therapy_clinic", "rambling_agency", "vague_baker",   # season
        "hvac_tech", "hvac_tech"]                                  # seasoned x2


def scorecard(state):
    model = WorkflowModel.from_dict(state.model_dict)
    steps = [n.label for n in model.nodes_of(NodeType.STEP)]
    burdens = sorted(((measure_burden(s, model), s) for s in steps), reverse=True)
    top2 = {s for _, s in burdens[:2]}
    fits = state.deliverable.get("where_ai_fits", [])
    solid = sum(1 for v in state.verdicts if v.verdict == "solid")
    return {
        "steps": len(steps),
        "opp": len(state.opportunities),
        "solid": solid,
        "verdicts": len(state.verdicts),
        "recs": len(fits),
        "lead_hits_top_burden": bool(fits) and fits[0]["step"] in top2,
        "timid_surviving": sum(1 for iv in state.interventions if is_timid(iv)),
    }


def mind_sizes():
    return {i.key: len(AgentMind.load(i.key).lessons) for i in ROSTER}


async def main():
    shutil.rmtree("firm_minds", ignore_errors=True)     # blank slate: job 1 is unseasoned
    print("minds wiped — starting blank", flush=True)
    for n, key in enumerate(JOBS, 1):
        sc = next(s for s in SCENARIOS if s.key == key)
        iv, sim = OllamaClient(), OllamaClient()
        t0 = time.monotonic()
        try:
            state = await run_pipeline(iv, sim, sc, clock=time.monotonic, max_turns=10)
            save_engagement(state, f"engagements/learning_job{n}_{key}")
            card = scorecard(state)
            card["secs"] = round(time.monotonic() - t0)
            print(f"JOB {n} {key}: {card} minds={mind_sizes()}", flush=True)
        except Exception as e:
            print(f"JOB {n} {key}: FAILED {type(e).__name__}: {str(e)[:120]}", flush=True)
        finally:
            await iv.close()
            await sim.close()

    print("\n=== FINAL MINDS (what the firm learned) ===", flush=True)
    for ident in ROSTER:
        m = AgentMind.load(ident.key)
        print(f"--- {ident.name} ({ident.key}) — {len(m.lessons)} lessons ---", flush=True)
        for l in m.lessons:
            print(f"  - {l.text[:150]}", flush=True)

asyncio.run(main())
print("SWEEP DONE", flush=True)
