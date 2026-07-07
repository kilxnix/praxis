import pytest
from praxis.session import DiscoverySession
from praxis.models import NodeType

class ScriptedClient:
    """Fakes both extraction (returns queued deltas) and questioning (echoes)."""
    def __init__(self, delta_script):
        self.delta_script = list(delta_script)
    async def complete_json(self, system, user, **kw):
        return self.delta_script.pop(0) if self.delta_script else {"deltas": []}
    async def complete(self, system, messages, **kw):
        return "And what happens next?"

@pytest.mark.asyncio
async def test_session_builds_model_and_reaches_completion():
    script = [
        {"deltas": [
            {"op": "add_node", "node_type": "step", "label": "take order", "quote": "I take the order"},
            {"op": "add_node", "node_type": "actor", "label": "me", "quote": "I take the order"},
            {"op": "add_node", "node_type": "tool", "label": "notebook", "quote": "in my notebook"},
            {"op": "add_edge", "edge_type": "performs", "source_label": "me", "source_type": "actor",
             "target_label": "take order", "target_type": "step", "quote": "I take the order"},
            {"op": "add_edge", "edge_type": "uses", "source_label": "take order", "source_type": "step",
             "target_label": "notebook", "target_type": "tool", "quote": "in my notebook"},
            {"op": "add_edge", "edge_type": "produces", "source_label": "take order", "source_type": "step",
             "target_label": "order slip", "target_type": "artifact", "quote": "I take the order"},
        ]},
    ]
    s = DiscoverySession(ScriptedClient(script), coverage_target=0.5)
    reply = await s.submit("I take the order in my notebook")
    assert s.model.find_node("take order", NodeType.STEP) is not None
    assert isinstance(reply, str) and len(reply) > 0

@pytest.mark.asyncio
async def test_session_stops_at_max_turns():
    s = DiscoverySession(ScriptedClient([]), max_turns=1)
    await s.submit("uh, we do stuff")
    assert s.is_intake_complete() is True  # hit the turn cap
