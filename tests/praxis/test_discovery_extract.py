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

@pytest.mark.asyncio
async def test_extract_drops_edge_with_missing_quote_key():
    payload = {"deltas": [
        {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
         "target_label": "x", "target_type": "step"},
    ]}
    assert await extract_deltas(FakeClient(payload), [], "msg", turn=1) == []

@pytest.mark.asyncio
async def test_extract_drops_whitespace_only_quote():
    payload = {"deltas": [{"op": "add_node", "node_type": "step", "label": "s", "quote": "   "}]}
    assert await extract_deltas(FakeClient(payload), [], "msg", turn=1) == []

@pytest.mark.asyncio
async def test_extract_drops_edge_with_invalid_endpoint_type():
    payload = {"deltas": [
        {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "bogus",
         "target_label": "x", "target_type": "step", "quote": "I do x"},
    ]}
    assert await extract_deltas(FakeClient(payload), [], "msg", turn=1) == []

@pytest.mark.asyncio
async def test_apply_deltas_skips_unresolvable_edge_without_crashing():
    m = WorkflowModel()
    deltas = [{"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "bogus",
               "target_label": "x", "target_type": "step", "quote": "q"}]
    apply_deltas(m, deltas, turn=1)  # must not raise
    assert len(m.edges) == 0

@pytest.mark.asyncio
async def test_apply_deltas_skips_edge_missing_quote_without_crashing():
    from praxis.models import WorkflowModel
    m = WorkflowModel()
    deltas = [{"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
               "target_label": "x", "target_type": "step"}]  # no quote key
    apply_deltas(m, deltas, turn=1)  # must not raise
    assert len(m.edges) == 0

@pytest.mark.asyncio
async def test_extract_tolerates_non_dict_and_unhashable_fields():
    payload = {"deltas": [
        "not a dict",
        {"op": "add_node", "node_type": ["step"], "label": "x", "quote": "q"},
        {"op": "add_node", "node_type": "step", "label": "ok", "quote": "we do ok"},
    ]}
    deltas = await extract_deltas(FakeClient(payload), [], "msg", turn=1)
    assert [d["label"] for d in deltas] == ["ok"]


@pytest.mark.asyncio
async def test_extract_deltas_handles_bare_list_result():
    # the local model sometimes returns a bare list instead of {"deltas":[...]} — don't crash
    class BareListClient:
        async def complete_json(self, system, user, **kw):
            return [{"op": "add_node", "node_type": "step", "label": "take order",
                     "quote": "I take the order"}]
    out = await extract_deltas(BareListClient(), [], "I take the order", 1)
    assert len(out) == 1 and out[0]["label"] == "take order"


@pytest.mark.asyncio
async def test_extract_deltas_handles_nonsense_result():
    class JunkClient:
        async def complete_json(self, system, user, **kw):
            return "not json at all"
    out = await extract_deltas(JunkClient(), [], "hi", 1)
    assert out == []
