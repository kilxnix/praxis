import json, pytest
from praxis.eval.scenarios import Scenario
from praxis.eval.harness import run_scenario, save_run

class InterviewerStub:
    async def complete_json(self, system, user, **kw):
        return {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "do the thing", "quote": "we do the thing"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "we do the thing"},
            {"op": "add_node", "node_type": "tool", "label": "sheet", "quote": "in a sheet"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "do the thing", "target_type": "step", "quote": "we do the thing"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "do the thing", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "in a sheet"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "do the thing", "source_type": "step",
             "target_label": "result", "target_type": "artifact", "quote": "we do the thing"},
        ]}
    async def complete(self, system, messages, **kw):
        return "What happens next?"

class SimStub:
    async def complete(self, system, messages, **kw):
        return "We do the thing in a sheet."

@pytest.mark.asyncio
async def test_run_scenario_and_save(tmp_path):
    sc = Scenario("t", "a test biz", "brief", "they do the thing in a sheet")
    ticks = iter([0.0, 4.2])
    res = await run_scenario(InterviewerStub(), SimStub(), sc,
                             clock=lambda: next(ticks), max_turns=5)
    assert res.turns >= 1
    assert res.seconds == 4.2
    path = save_run(res, str(tmp_path))
    saved = json.loads(open(path).read())
    assert saved["scenario_key"] == "t"
    assert saved["metrics"]["seconds"] == 4.2
    assert "nodes" in saved["model"]
