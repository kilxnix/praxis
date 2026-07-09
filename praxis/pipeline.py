"""End-to-end Praxis pipeline: run a Discovery interview, then the diagnostic firm, and
persist the whole engagement (map + transcript + every agent action/hand-off + deliverable).
For a repeatable run the interview happens against a simulated client; in production the
interviewer talks to a real client and the firm is identical."""
import json
import os
from praxis.models import WorkflowModel
from praxis.eval.harness import run_scenario
from praxis.firm import run_firm
from praxis.firm_agent import reflect_firm
from praxis.principal import synthesize
from praxis.render import to_markdown


async def finalize(interviewer_client, model, firm, transcript, business_label):
    """Take a finished Discovery map (+ the firm that sat in) through the diagnostic firm,
    synthesize the owner-facing deliverable, and let the firm learn. Shared by the simulated
    pipeline AND the live web app, so both produce identical output. Returns EngagementState."""
    state = await run_firm(interviewer_client, model, firm=firm, business_label=business_label,
                           transcript=transcript)
    state.transcript = transcript
    state.deliverable = await synthesize(interviewer_client, transcript, state.deliverable)
    state.record("principal", "synthesized",
                 "translated the plan into owner-facing pains, a summary, and outcomes",
                 consumed_from="discovery+all")
    learned = await reflect_firm(firm, business_label)
    state.record("principal", "firm_reflected",
                 f"the firm distilled {learned} durable lessons into their minds",
                 consumed_from="all", count=learned)
    state.firm = firm          # transient handle so the saver can write the employees' work
    return state


async def run_pipeline(interviewer_client, sim_client, scenario, clock, max_turns=25):
    """Interview (simulated client) -> workflow map -> firm -> deliverable. Returns EngagementState."""
    run = await run_scenario(interviewer_client, sim_client, scenario, clock,
                             max_turns=max_turns, coverage_target=1.0, live_firm=True)
    model = WorkflowModel.from_dict(run.model_dict)
    return await finalize(interviewer_client, model, run.firm, run.transcript, scenario.key)


def save_engagement(state, out_dir, firm=None):
    """Persist one engagement into its OWN folder: the readable deliverable, the full recorded
    state (JSON), and — if the firm worked it — a firm/ folder with one file per employee showing
    who they became for this business, what they understood, and what they carry forward."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "engagement.json"), "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)
    with open(os.path.join(out_dir, "deliverable.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(state.deliverable))

    firm = firm if firm is not None else getattr(state, "firm", None)
    if firm:
        firm_dir = os.path.join(out_dir, "firm")
        os.makedirs(firm_dir, exist_ok=True)
        for key, agent in firm.items():
            beliefs = [f"- {b.note}" for b in agent.memory.beliefs] or ["_(nothing)_"]
            lessons = [f"- {l.text}" for l in agent.mind.lessons] or ["_(none yet)_"]
            doc = (f"# {agent.identity.name} — {agent.identity.role}\n\n"
                   f"_{agent.identity.voice}_\n\n"
                   f"## Who I became for this business\n{agent.stance or '_(no stance)_'}\n\n"
                   f"## What I understood about this business\n" + "\n".join(beliefs) + "\n\n"
                   f"## What I carry forward (my mind)\n" + "\n".join(lessons) + "\n")
            with open(os.path.join(firm_dir, f"{key}.md"), "w", encoding="utf-8") as f:
                f.write(doc)
    return out_dir
