import pytest
from praxis.models import WorkflowModel, NodeType
from praxis.discovery import extract_deltas, apply_deltas

class FakeClient:
    def __init__(self, payload): self.payload = payload
    async def complete_json(self, system, user, **kw): return self.payload

@pytest.mark.asyncio
async def test_grain_guard_drops_fragment_steps():
    payload = {"deltas": [
        {"op": "add_node", "node_type": "step", "label": "take order", "quote": "I take the order"},
        {"op": "add_node", "node_type": "step",
         "label": "hoping someone actually ordered scones", "quote": "hoping someone ordered"},
    ]}
    deltas = await extract_deltas(FakeClient(payload), [], "msg", turn=1)
    labels = [d["label"] for d in deltas if d["op"] == "add_node"]
    assert "take order" in labels
    assert "hoping someone actually ordered scones" not in labels

@pytest.mark.asyncio
async def test_canonical_dedup_merges_surface_variants():
    m = WorkflowModel()
    deltas = [
        {"op": "add_node", "node_type": "tool", "label": "the notebook", "quote": "the notebook"},
        {"op": "add_node", "node_type": "tool", "label": "my notebook", "quote": "my notebook"},
        {"op": "add_node", "node_type": "tool", "label": "notebook", "quote": "a notebook"},
    ]
    apply_deltas(m, deltas, turn=1)
    assert len(m.nodes_of(NodeType.TOOL)) == 1   # all collapse to one canonical node
