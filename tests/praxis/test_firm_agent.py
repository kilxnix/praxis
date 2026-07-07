import pytest
from praxis.firm_agent import (FirmAgent, AgentMind, Identity, assemble_firm, reflect_firm)


IDENT = Identity("skeptic", "Idris", "skeptic", "You guard the owner.")


class _Client:
    """Routes by prompt: reflect -> a lesson; morph -> a stance; observe -> a belief."""
    async def complete_json(self, system, user, **kw):
        s = system.lower()
        if "durable lessons" in s or "transferable lesson" in s:
            return {"lessons": ["owners who bill at night are the ones who fear errors most"]}
        if "synthesize" in s or "reasoning stance" in s:
            return {"stance": "This is a solo operator who guards his paper book; I will weight "
                               "adoption friction and distrust anything that makes him stop mid-job."}
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


@pytest.mark.asyncio
async def test_morph_synthesizes_a_stance_that_leads_understanding(tmp_path):
    agent = FirmAgent(IDENT, _Client(), AgentMind("skeptic", path=str(tmp_path / "skeptic.json")))
    await agent.observe("Interviewer: how do you bill?\nOwner: I type it in at night", "", 1)
    assert agent.stance == ""                                  # no synthesis yet — only ingested
    stance = await agent.morph("some_hvac")
    assert "solo operator" in stance                           # processed into a coherent stance
    u = agent.understanding()
    assert u.startswith("HOW YOU'VE SIZED UP THIS BUSINESS")   # decisions reason from the morph first
    assert "solo operator" in u


def test_assemble_firm_loads_persisted_minds(tmp_path):
    AgentMind("analyst", path=str(tmp_path / "analyst.json"))  # nothing saved yet
    m = AgentMind.load("analyst", str(tmp_path))
    m.add_lesson("listen for the sigh behind a sentence")
    m.save()
    firm = assemble_firm(_Client(), minds_dir=str(tmp_path))
    assert any("sigh" in l.text for l in firm["analyst"].mind.lessons)   # seasoned on assembly
    assert firm["skeptic"].mind.lessons == []                            # unseasoned role is blank
