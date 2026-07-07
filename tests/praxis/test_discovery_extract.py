import pytest
from praxis.models import WorkflowModel, NodeType
from praxis.discovery import extract_deltas, apply_deltas

class FakeClient:
    def __init__(self, payload): self.payload = payload
    async def complete_json(self, system, user, **kw): return self.payload

@pytest.mark.asyncio
async def test_extract_drops_evidenceless_deltas():
    payload = {"deltas": [
        {"op": "add_node", "node_type": "step", "label": "send quote", "quote": "then I send them a quote"},
        {"op": "add_node", "node_type": "step", "label": "hallucinated step", "quote": ""},
    ]}
    deltas = await extract_deltas(FakeClient(payload), [], "then I send them a quote", turn=1)
    labels = [d["label"] for d in deltas]
    assert "send quote" in labels
    assert "hallucinated step" not in labels  # evidence-required drop

@pytest.mark.asyncio
async def test_apply_deltas_reuses_nodes_and_links_edges():
    m = WorkflowModel()
    deltas = [
        {"op": "add_node", "node_type": "actor", "label": "me", "quote": "I do it"},
        {"op": "add_node", "node_type": "step", "label": "send quote", "quote": "I send a quote"},
        {"op": "add_edge", "edge_type": "performs",
         "source_label": "me", "source_type": "actor",
         "target_label": "send quote", "target_type": "step", "quote": "I send a quote"},
    ]
    apply_deltas(m, deltas, turn=1)
    assert m.find_node("me", NodeType.ACTOR) is not None
    assert len(m.edges) == 1
