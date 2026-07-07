import pytest
from praxis.eval.scenarios import SCENARIOS, Scenario
from praxis.eval.client_sim import simulated_reply

def test_scenarios_are_well_formed():
    keys = {s.key for s in SCENARIOS}
    assert {"vague_baker", "rambling_agency", "jargon_manufacturer", "defensive_founder"} <= keys
    for s in SCENARIOS:
        assert s.business and s.persona and s.truth

class FakeClient:
    def __init__(self): self.saw = None
    async def complete(self, system, messages, **kw):
        self.saw = system
        return "I dunno, we just kind of get the orders done."

@pytest.mark.asyncio
async def test_simulated_reply_uses_persona_system():
    fc = FakeClient()
    sc = SCENARIOS[0]
    out = await simulated_reply(fc, sc, "Walk me through your day.", [])
    assert sc.persona[:12] in fc.saw   # persona injected into the sim's system prompt
    assert isinstance(out, str) and out
