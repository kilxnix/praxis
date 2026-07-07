"""End-to-end Praxis pipeline: run a Discovery interview, then the diagnostic firm, and
persist the whole engagement (map + transcript + every agent action/hand-off + deliverable).
For a repeatable run the interview happens against a simulated client; in production the
interviewer talks to a real client and the firm is identical."""
import json
import os
from praxis.models import WorkflowModel
from praxis.eval.harness import run_scenario
from praxis.firm import run_firm
from praxis.render import to_markdown


async def run_pipeline(interviewer_client, sim_client, scenario, clock, max_turns=25):
    """Interview -> workflow map -> firm -> deliverable. Returns the EngagementState."""
    run = await run_scenario(interviewer_client, sim_client, scenario, clock,
                             max_turns=max_turns, coverage_target=1.0)
    model = WorkflowModel.from_dict(run.model_dict)
    state = await run_firm(interviewer_client, model)
    state.transcript = run.transcript
    return state


def save_engagement(state, out_dir):
    """Persist the full engagement: the recorded state (JSON) and the readable deliverable."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "engagement.json"), "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)
    with open(os.path.join(out_dir, "deliverable.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(state.deliverable))
    return out_dir
