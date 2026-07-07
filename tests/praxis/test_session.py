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
    s = DiscoverySession(ScriptedClient(script), coverage_target=0.5, live_firm=False)
    reply = await s.submit("I take the order in my notebook")
    assert s.model.find_node("take order", NodeType.STEP) is not None
    assert isinstance(reply, str) and len(reply) > 0

@pytest.mark.asyncio
async def test_session_stops_at_max_turns():
    s = DiscoverySession(ScriptedClient([]), max_turns=1, live_firm=False)
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
    s = DiscoverySession(ScriptedClient([]), max_turns=1, live_firm=False)
    reply = await s.submit("uh we do stuff")
    assert reply == CLOSING
    assert s.history[-1]["content"] == CLOSING


def test_saturated_needs_min_steps_even_with_full_coverage():
    s = DiscoverySession(ScriptedClient([]), coverage_target=0.8,
                         min_steps=3, saturation_gap=4)
    for lbl in ("one", "two"):
        _satisfied_step(s.model, lbl)
    s.turn, s.last_new_step_turn = 10, 0     # saturated, but only 2 steps
    assert s._saturated() is False           # under min_steps -> not a stop candidate
    _satisfied_step(s.model, "three")        # now 3 satisfied steps
    assert s._saturated() is True            # >= min_steps + full coverage + saturated


def test_not_saturated_until_gap():
    s = DiscoverySession(ScriptedClient([]), coverage_target=0.8,
                         min_steps=3, saturation_gap=4)
    for lbl in ("one", "two", "three"):
        _satisfied_step(s.model, lbl)
    s.turn, s.last_new_step_turn = 5, 4      # only 1 turn since a new step surfaced
    assert s._saturated() is False
    s.last_new_step_turn = 1                 # 4 turns since the last new step
    assert s._saturated() is True


def test_not_saturated_when_coverage_below_target():
    s = DiscoverySession(ScriptedClient([]), coverage_target=0.8)
    # two bare STEP nodes -> coverage 0.0 -> not a stop candidate
    s.model.add_node(NodeType.STEP, "a", [Evidence("q", 1)])
    s.model.add_node(NodeType.STEP, "b", [Evidence("q", 1)])
    assert s._saturated() is False


@pytest.mark.asyncio
async def test_transcript_starts_with_opening_line():
    s = DiscoverySession(ScriptedClient([]), max_turns=2, live_firm=False)
    assert s.history[0] == {"role": "assistant", "content": OPENING}
    await s.submit("we take orders")
    assert s.history[0]["content"] == OPENING   # opener preserved at the front


class _GateClient:
    """Returns empty deltas, then a controllable completeness verdict, then a question."""
    def __init__(self, complete_flag):
        self.jsons = [{"deltas": []}, {"complete": complete_flag, "missing": "the end"}]
        self.i = 0
    async def complete_json(self, system, user, **kw):
        r = self.jsons[self.i] if self.i < len(self.jsons) else {"deltas": []}
        self.i += 1
        return r
    async def complete(self, system, messages, **kw):
        return "what happens at the very end?"


@pytest.mark.asyncio
async def test_completeness_gate_keeps_going_when_incomplete():
    s = DiscoverySession(_GateClient(False), min_steps=2, saturation_gap=0, coverage_target=0.8, live_firm=False)
    for lbl in ("one", "two"):
        _satisfied_step(s.model, lbl)
    s.turn, s.last_new_step_turn = 4, 0          # will be saturated after this turn
    reply = await s.submit("more info")
    assert reply != CLOSING                       # saturated but NOT the whole job -> keep going
    assert s._closed is False
    assert s.completeness_extensions == 1


@pytest.mark.asyncio
async def test_completeness_gate_closes_when_whole_job_mapped():
    s = DiscoverySession(_GateClient(True), min_steps=2, saturation_gap=0, coverage_target=0.8, live_firm=False)
    for lbl in ("one", "two"):
        _satisfied_step(s.model, lbl)
    s.turn, s.last_new_step_turn = 4, 0
    reply = await s.submit("more info")
    assert reply == CLOSING                       # saturated AND complete -> conclude
    assert s.is_intake_complete() is True


class _FirmClient:
    """Routes by prompt: the firm's observe prompt asks for 'beliefs', everything else deltas."""
    async def complete_json(self, system, user, **kw):
        if "beliefs" in system:
            return {"beliefs": [{"note": "they copy leads by hand",
                                 "grounds": "I copy each lead into a spreadsheet"}]}
        return {"deltas": []}
    async def complete(self, system, messages, **kw):
        return "what happens next?"


@pytest.mark.asyncio
async def test_firm_memory_grows_during_interview():
    s = DiscoverySession(_FirmClient(), max_turns=5)      # live_firm on by default
    assert s.firm is not None
    assert all(a.memory.is_empty() for a in s.firm.values())   # blank slate before the interview
    await s.submit("I copy each lead into a spreadsheet by hand")
    # every member watched the exchange and formed their own understanding of this business
    assert all(not a.memory.is_empty() for a in s.firm.values())
    assert "lead" in s.firm["skeptic"].memory.recall().lower()
