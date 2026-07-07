import json, pytest
import praxis.eval.run_phase0 as r0
from praxis.eval.scenarios import Scenario

class InterviewerStub:
    async def complete_json(self, system, user, **kw):
        return {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "do it", "quote": "we do it"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "we do it"},
            {"op": "add_node", "node_type": "tool", "label": "sheet", "quote": "a sheet"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "do it", "target_type": "step", "quote": "we do it"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "do it", "source_type": "step",
             "target_label": "sheet", "target_type": "tool", "quote": "a sheet"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "do it", "source_type": "step",
             "target_label": "out", "target_type": "artifact", "quote": "we do it"},
        ]}
    async def complete(self, system, messages, **kw): return "Next?"
    async def close(self): pass

class SimStub:
    async def complete(self, system, messages, **kw): return "We do it in a sheet."
    async def close(self): pass

@pytest.mark.asyncio
async def test_main_writes_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(r0, "_make_client", lambda: InterviewerStub())
    monkeypatch.setattr(r0, "_make_sim_client", lambda: SimStub())
    monkeypatch.setattr(r0, "SCENARIOS", [Scenario("solo", "biz", "brief", "they do it in a sheet")])
    rep = await r0.main(out_dir=str(tmp_path))
    assert (tmp_path / "gate_report.json").exists()
    assert (tmp_path / "scorecards.json").exists()
    assert rep["n"] == 1
