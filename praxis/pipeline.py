"""End-to-end Praxis pipeline: run a Discovery interview, then the diagnostic firm,
producing the finished deliverable. For a watchable, repeatable run the interview happens
against a simulated client; in production the interviewer talks to a real client and the
firm stages are identical."""
from praxis.models import WorkflowModel
from praxis.eval.harness import run_scenario
from praxis.firm import run_firm


async def run_pipeline(interviewer_client, sim_client, scenario, clock, max_turns=25):
    """Interview -> workflow map -> firm -> deliverable.
    Returns (run_result, model, deliverable)."""
    run = await run_scenario(interviewer_client, sim_client, scenario, clock,
                             max_turns=max_turns, coverage_target=1.0)
    model = WorkflowModel.from_dict(run.model_dict)
    deliverable = await run_firm(interviewer_client, model)
    return run, model, deliverable
