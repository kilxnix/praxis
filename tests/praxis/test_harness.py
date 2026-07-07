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


class CoverageCompletingStub:
    async def complete_json(self, system, user, **kw):
        return {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "A", "quote": "we do A"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "we do A"},
            {"op": "add_node", "node_type": "tool", "label": "sheet", "quote": "a sheet"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "A", "target_type": "step", "quote": "we do A"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "A", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "a sheet"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "A", "source_type": "step",
             "target_label": "outA", "target_type": "artifact", "quote": "we do A"},
            {"op": "add_node", "node_type": "step", "label": "B", "quote": "then B"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "B", "target_type": "step", "quote": "then B"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "B", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "then B"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "B", "source_type": "step",
             "target_label": "outB", "target_type": "artifact", "quote": "then B"},
            {"op": "add_node", "node_type": "step", "label": "C", "quote": "lastly C"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "C", "target_type": "step", "quote": "lastly C"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "C", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "lastly C"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "C", "source_type": "step",
             "target_label": "outC", "target_type": "artifact", "quote": "lastly C"},
            {"op": "add_node", "node_type": "step", "label": "D", "quote": "then D"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "D", "target_type": "step", "quote": "then D"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "D", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "then D"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "D", "source_type": "step",
             "target_label": "outD", "target_type": "artifact", "quote": "then D"},
        ]}
    async def complete(self, system, messages, **kw):
        return "what next?"


@pytest.mark.asyncio
async def test_run_scenario_completes_via_coverage_not_maxturns():
    # Stub surfaces 3 fully-satisfied steps on turn 1 and nothing new after, so the
    # session completes once saturated (>= min_steps, coverage 1.0, no new steps for
    # saturation_gap turns) — well before the 25-turn cap.
    sc = Scenario("cov", "biz", "brief", "A then B then C in a sheet")
    ticks = iter([0.0, 1.0])
    res = await run_scenario(CoverageCompletingStub(), SimStub(), sc,
                             clock=lambda: next(ticks), max_turns=25)
    assert 1 <= res.turns < 25   # exited via coverage+saturation, not the turn cap
