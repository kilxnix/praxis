import pytest
from praxis.models import WorkflowModel, NodeType, Evidence
from praxis.discovery import next_question

class FocusCapturingClient:
    def __init__(self): self.last_user = None
    async def complete(self, system, messages, **kw):
        self.last_user = messages[-1]["content"]
        return "So what tool do you use to take the order?"

@pytest.mark.asyncio
async def test_next_question_routes_through_a_play():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "take order", [Evidence("we take orders", 1)])
    fc = FocusCapturingClient()
    q, intent = await next_question(fc, m, [{"role": "user", "content": "we take orders"}])
    # complete_step_facets fires: the directive names the step + a facet
    assert "take order" in fc.last_user
    assert q.endswith("?")
    assert intent and intent["step_label"] == "take order"   # intent captured for extraction

class FakeClient:
    def __init__(self): self.last_user = None
    async def complete(self, system, messages, **kw):
        self.last_user = messages[-1]["content"]
        return "Who actually files it, and what do they file it in?"

@pytest.mark.asyncio
async def test_next_question_passes_focus_to_model():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "file it", [Evidence("then we file it", 1)])
    fc = FakeClient()
    q, _ = await next_question(fc, m, [{"role": "user", "content": "then we file it"}])
    assert "file it" in fc.last_user       # focus hint reached the model
    assert q.endswith("?")
