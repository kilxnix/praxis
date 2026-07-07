import pytest
from praxis.firm_agent import (FirmAgent, AgentMind, Identity, assemble_firm, reflect_firm)


IDENT = Identity("skeptic", "Idris", "skeptic", "You guard the owner.")


class _Client:
    """observe -> a belief; reflect -> a durable lesson."""
    async def complete_json(self, system, user, **kw):
        if "durable lessons" in system.lower() or "transferable lesson" in system.lower():
            return {"lessons": ["owners who bill at night are the ones who fear errors most"]}
        return {"beliefs": [{"note": "they re-key everything by hand at night",
                             "grounds": "I type it all into QuickBooks"}]}
    async def complete(self, system, messages, **kw):
        return "q"


@pytest.mark.asyncio
async def test_reflect_forms_lessons_and_persists(tmp_path):
    path = str(tmp_path / "skeptic.json")
    agent = FirmAgent(IDENT, _Client(), AgentMind("skeptic", path=path))
    await agent.observe("Interviewer: how do you bill?\nOwner: I type it all in at night", "", 1)
    assert not agent.memory.is_empty()
    added = await agent.reflect("some_hvac")
    assert added == 1
    assert "fear errors" in agent.mind.recall()
    # a fresh mind loaded from disk carries the lesson forward — it was learned, not just held
    reloaded = AgentMind.load("skeptic", str(tmp_path))
    assert any("fear errors" in l.text for l in reloaded.lessons)


@pytest.mark.asyncio
async def test_understanding_is_compact_and_uses_mind(tmp_path):
    mind = AgentMind("skeptic", [], str(tmp_path / "skeptic.json"))
    mind.add_lesson("watch for single points of failure", "past_job")
    agent = FirmAgent(IDENT, _Client(), mind)
    for i in range(20):                                   # a big verbose pile of this-business beliefs
        agent.memory.remember(f"belief number {i} about the business", f"quote {i}", i)
    u = agent.understanding(max_notes=8)
    assert "single points of failure" in u               # the learned mind feeds the decision
    assert u.count("belief number") <= 8                  # capped, not the whole verbose wall


def test_assemble_firm_loads_persisted_minds(tmp_path):
    AgentMind("analyst", path=str(tmp_path / "analyst.json"))  # nothing saved yet
    m = AgentMind.load("analyst", str(tmp_path))
    m.add_lesson("listen for the sigh behind a sentence")
    m.save()
    firm = assemble_firm(_Client(), minds_dir=str(tmp_path))
    assert any("sigh" in l.text for l in firm["analyst"].mind.lessons)   # seasoned on assembly
    assert firm["skeptic"].mind.lessons == []                            # unseasoned role is blank
