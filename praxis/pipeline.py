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


async def finalize(interviewer_client, model, firm, transcript, business_label, fixtures=None,
                   core_steps=None):
    """Take a finished Discovery map (+ the firm that sat in) through the diagnostic firm,
    synthesize the owner-facing deliverable, and let the firm learn. Shared by the simulated
    pipeline AND the live web app, so both produce identical output. `fixtures` are the real
    data samples (ground truth for SP2); `core_steps` are the business's core value work so the
    firm prioritizes it. Returns EngagementState."""
    state = await run_firm(interviewer_client, model, firm=firm, business_label=business_label,
                           transcript=transcript, core_steps=core_steps)
    state.transcript = transcript
    state.fixtures = list(fixtures or [])
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
    return await finalize(interviewer_client, model, run.firm, run.transcript, scenario.key,
                          fixtures=getattr(run, "fixtures", None),
                          core_steps=getattr(run, "core_step_labels", None))


def build_handoff(state):
    """The explicit SP1 -> SP2 contract. SP2's Solutioner consumes THIS, not the whole
    engagement: the recommended interventions that are actually BUILDABLE (carry trigger / I/O /
    success-criteria), plus the real fixtures (ground truth) its Airlock Verifier tests against.
    Interventions missing the buildable spec are listed separately as not-yet-buildable, so the
    boundary is honest — SP2 never silently compiles prose."""
    from dataclasses import asdict
    recs = state.deliverable.get("where_ai_fits", [])
    buildable = [r for r in recs if r.get("buildable")]
    not_buildable = [r["step"] for r in recs if not r.get("buildable")]
    return {
        "business": state.deliverable.get("summary", "")[:200],
        "buildable_interventions": [
            {k: r.get(k) for k in ("step", "what_it_does", "trigger", "input_source",
                                   "output_dest", "success_criteria")}
            for r in buildable],
        "not_yet_buildable": not_buildable,     # recommended but lacking a compilable spec
        "fixtures": [asdict(f) for f in state.fixtures],
        "ready_for_sp2": bool(buildable) and bool(state.fixtures),
    }


def save_engagement(state, out_dir, firm=None):
    """Persist one engagement into its OWN folder: the readable deliverable, the full recorded
    state (JSON), the SP1->SP2 build handoff, and — if the firm worked it — a firm/ folder with
    one file per employee showing who they became, understood, and carry forward."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "engagement.json"), "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)
    with open(os.path.join(out_dir, "deliverable.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(state.deliverable))
    with open(os.path.join(out_dir, "build_handoff.json"), "w", encoding="utf-8") as f:
        json.dump(build_handoff(state), f, indent=2)

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
