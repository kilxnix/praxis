import pytest
from praxis.models import WorkflowModel, NodeType, Evidence
from praxis.discovery import next_question, focus_hint_for

def test_focus_hint_targets_the_biggest_gap():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "file it", [Evidence("then we file it", 1)])
    hint = focus_hint_for(m)
    assert "file it" in hint
    assert "who" in hint.lower()

def test_focus_hint_when_no_gaps_asks_sequence_or_pain():
    hint = focus_hint_for(WorkflowModel())
    assert "painful" in hint.lower() or "after" in hint.lower()

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
    q = await next_question(fc, m, [{"role": "user", "content": "then we file it"}])
    assert "file it" in fc.last_user       # focus hint reached the model
    assert q.endswith("?")
