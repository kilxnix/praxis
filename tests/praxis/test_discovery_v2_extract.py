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

@pytest.mark.asyncio
async def test_fragment_step_not_recreated_via_edge_endpoint():
    m = WorkflowModel()
    deltas = [
        {"op": "add_edge", "edge_type": "performs",
         "source_label": "me", "source_type": "actor",
         "target_label": "hoping someone actually ordered scones", "target_type": "step",
         "quote": "hoping someone ordered"},
    ]
    apply_deltas(m, deltas, turn=1)
    assert len(m.nodes_of(NodeType.STEP)) == 0  # fragment step must NOT enter via the edge path

@pytest.mark.asyncio
async def test_valid_step_endpoint_still_created_via_edge():
    m = WorkflowModel()
    deltas = [
        {"op": "add_edge", "edge_type": "uses",
         "source_label": "take order", "source_type": "step",
         "target_label": "notebook", "target_type": "tool", "quote": "in my notebook"},
    ]
    apply_deltas(m, deltas, turn=1)
    assert len(m.nodes_of(NodeType.STEP)) == 1  # valid short step endpoint IS created


@pytest.mark.asyncio
async def test_extract_deltas_threads_focus_into_prompt():
    captured = {}

    class Cap:
        async def complete_json(self, system, user, **kw):
            captured["user"] = user
            return {"deltas": []}

    await extract_deltas(Cap(), [], "the account manager does it", turn=1,
                         focus={"step_label": "draft proposal", "facet": "actor"})
    assert "you_just_asked_about" in captured["user"]
    assert "draft proposal" in captured["user"]   # intent reached the extractor
