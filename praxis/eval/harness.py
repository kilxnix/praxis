"""Run one Discovery interview against a simulated client and persist everything the
Phase 0 gate needs to judge it: transcript, graph, turns, wall-clock."""
import json
import os
from dataclasses import dataclass, field
from praxis.session import DiscoverySession
from praxis.eval.client_sim import simulated_reply


@dataclass
class RunResult:
    scenario_key: str
    transcript: list = field(default_factory=list)
    model_dict: dict = field(default_factory=dict)
    turns: int = 0
    seconds: float = 0.0


async def run_scenario(interviewer_client, client_sim_client, scenario, clock, max_turns=25,
                       coverage_target=0.8):
    session = DiscoverySession(interviewer_client, max_turns=max_turns,
                               coverage_target=coverage_target)
    start = clock()
    interviewer_line = session.opening_line()
    sim_history = []
    while not session.is_intake_complete():
        client_msg = await simulated_reply(client_sim_client, scenario, interviewer_line, sim_history)
        sim_history.append({"role": "user", "content": interviewer_line})
        sim_history.append({"role": "assistant", "content": client_msg})
        interviewer_line = await session.submit(client_msg)
    seconds = clock() - start
    return RunResult(
        scenario_key=scenario.key,
        transcript=session.history,
        model_dict=session.model.to_dict(),
        turns=session.turn,
        seconds=seconds,
    )


def save_run(result: RunResult, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{result.scenario_key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario_key": result.scenario_key,
            "transcript": result.transcript,
            "model": result.model_dict,
            "metrics": {"turns": result.turns, "seconds": result.seconds},
        }, f, indent=2)
    return path
