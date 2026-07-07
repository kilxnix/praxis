import pytest
from praxis.session import DiscoverySession, CLOSING, OPENING
from praxis.models import NodeType, EdgeType, Evidence

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


def _satisfied_step(m, name):
    def ev():
        return [Evidence("q", 1)]
    s = m.add_node(NodeType.STEP, name, ev())
    a = m.add_node(NodeType.ACTOR, name + "_a", ev())
    t = m.add_node(NodeType.TOOL, name + "_t", ev())
    o = m.add_node(NodeType.ARTIFACT, name + "_o", ev())
    m.add_edge(EdgeType.PERFORMS, a.id, s.id, ev())
    m.add_edge(EdgeType.USES, s.id, t.id, ev())
    m.add_edge(EdgeType.PRODUCES, s.id, o.id, ev())
    return s


@pytest.mark.asyncio
async def test_closing_branch_fires_and_is_returned():
    s = DiscoverySession(ScriptedClient([]), max_turns=1)
    reply = await s.submit("uh we do stuff")
    assert reply == CLOSING
    assert s.history[-1]["content"] == CLOSING


def test_intake_needs_min_steps_even_with_full_coverage():
    s = DiscoverySession(ScriptedClient([]), coverage_target=0.8,
                         min_steps=3, saturation_gap=4)
    for lbl in ("one", "two"):
        _satisfied_step(s.model, lbl)
    s.turn, s.last_new_step_turn = 10, 0     # saturated, but only 2 steps
    assert s.is_intake_complete() is False   # under min_steps -> not done
    _satisfied_step(s.model, "three")        # now 3 satisfied steps
    assert s.is_intake_complete() is True     # >= min_steps + full coverage + saturated


def test_intake_incomplete_until_saturated():
    s = DiscoverySession(ScriptedClient([]), coverage_target=0.8,
                         min_steps=3, saturation_gap=4)
    for lbl in ("one", "two", "three"):
        _satisfied_step(s.model, lbl)
    s.turn, s.last_new_step_turn = 5, 4      # only 1 turn since a new step surfaced
    assert s.is_intake_complete() is False   # not yet saturated
    s.last_new_step_turn = 1                 # 4 turns since the last new step
    assert s.is_intake_complete() is True


def test_intake_incomplete_when_coverage_below_target():
    s = DiscoverySession(ScriptedClient([]), coverage_target=0.8)
    # two steps but only bare STEP nodes -> coverage 0.0 -> not complete
    s.model.add_node(NodeType.STEP, "a", [Evidence("q", 1)])
    s.model.add_node(NodeType.STEP, "b", [Evidence("q", 1)])
    assert s.is_intake_complete() is False


@pytest.mark.asyncio
async def test_transcript_starts_with_opening_line():
    s = DiscoverySession(ScriptedClient([]), max_turns=2)
    assert s.history[0] == {"role": "assistant", "content": OPENING}
    await s.submit("we take orders")
    assert s.history[0]["content"] == OPENING   # opener preserved at the front
