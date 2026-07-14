"""The training loop: sequencing, learning, resilience, and pacing — exercised with an injected
engagement runner so no local model is needed. The real runner (run_pipeline) is covered by the
firm/pipeline tests; here we prove the LOOP around it behaves."""
import json
import os
from types import SimpleNamespace

import pytest

from praxis import train as T
from praxis.firm_agent import AgentMind


def _grow(minds_dir, key, text):
    """Simulate what reflect_firm does at the end of a real engagement: add a durable lesson to
    an employee's mind and persist it."""
    m = AgentMind.load(key, minds_dir)
    m.add_lesson(text, "test")
    m.save()


async def _nosleep(_):
    pass


def _ledger(minds_dir):
    path = os.path.join(minds_dir, "training_log.jsonl")
    return [json.loads(x) for x in open(path, encoding="utf-8").read().splitlines() if x.strip()]


@pytest.mark.asyncio
async def test_loop_runs_every_business_and_learns(tmp_path):
    minds = str(tmp_path / "minds")
    pool = [SimpleNamespace(key="alpha"), SimpleNamespace(key="beta")]
    seen = []

    async def run_one(sc):
        seen.append(sc.key)
        _grow(minds, "analyst", f"lesson from {sc.key} #{len(seen)}")

    n = await T.train(count=4, interval=0, minds_dir=minds, pool=pool,
                      run_one=run_one, sleep=_nosleep, log=lambda *_: None)

    assert n == 4
    assert seen == ["alpha", "beta", "alpha", "beta"]          # cycles through the pool in order
    assert len(AgentMind.load("analyst", minds).lessons) == 4  # every engagement grew the mind

    recs = _ledger(minds)
    assert len(recs) == 4
    assert all(r["ok"] for r in recs)
    assert recs[0]["new"]["analyst"] == 1                      # per-engagement growth recorded
    assert recs[3]["minds"]["analyst"] == 4                    # cumulative size recorded


@pytest.mark.asyncio
async def test_numbering_continues_across_restarts(tmp_path):
    minds = str(tmp_path / "minds")
    pool = [SimpleNamespace(key="a")]

    async def run_one(sc):
        pass

    await T.train(count=2, interval=0, minds_dir=minds, pool=pool,
                  run_one=run_one, sleep=_nosleep, log=lambda *_: None)
    await T.train(count=2, interval=0, minds_dir=minds, pool=pool,   # a second, separate run
                  run_one=run_one, sleep=_nosleep, log=lambda *_: None)

    ns = [r["n"] for r in _ledger(minds)]
    assert ns == [1, 2, 3, 4]      # the restart picks up at 3, not back at 1


@pytest.mark.asyncio
async def test_a_failed_engagement_does_not_kill_the_loop(tmp_path):
    minds = str(tmp_path / "minds")
    pool = [SimpleNamespace(key="good"), SimpleNamespace(key="bad")]

    async def run_one(sc):
        if sc.key == "bad":
            raise RuntimeError("model timeout")
        _grow(minds, "skeptic", "held up")

    n = await T.train(count=4, interval=0, minds_dir=minds, pool=pool,
                      run_one=run_one, sleep=_nosleep, log=lambda *_: None)

    assert n == 4                                              # loop kept going past the failure
    recs = _ledger(minds)
    assert recs[0]["ok"] is True
    assert recs[1]["ok"] is False
    assert "model timeout" in recs[1]["error"]
    assert len(AgentMind.load("skeptic", minds).lessons) == 2  # the good runs still learned


@pytest.mark.asyncio
async def test_pauses_between_engagements_but_not_after_the_last(tmp_path):
    minds = str(tmp_path / "minds")
    pool = [SimpleNamespace(key="a")]
    sleeps = []

    async def run_one(sc):
        pass

    async def record_sleep(seconds):
        sleeps.append(seconds)

    await T.train(count=3, interval=7, minds_dir=minds, pool=pool,
                  run_one=run_one, sleep=record_sleep, log=lambda *_: None)

    assert sleeps == [7, 7]      # count-1 pauses; no wasted wait after the final engagement


@pytest.mark.asyncio
async def test_shuffle_covers_the_whole_pool(tmp_path):
    minds = str(tmp_path / "minds")
    pool = [SimpleNamespace(key=f"biz{i}") for i in range(5)]
    seen = []

    async def run_one(sc):
        seen.append(sc.key)

    await T.train(count=5, interval=0, minds_dir=minds, pool=pool, shuffle=True,
                  run_one=run_one, sleep=_nosleep, log=lambda *_: None)

    assert sorted(seen) == [f"biz{i}" for i in range(5)]   # a shuffled pass still hits each once


def test_status_reports_each_employee(tmp_path):
    minds = str(tmp_path / "minds")
    _grow(minds, "principal", "protect the owner's time above all")
    report = T.status(minds)
    assert "Dana" in report and "principal" in report
    assert "protect the owner's time above all" in report
    assert "Idris" in report            # every roster member is listed, even at zero lessons


def test_mind_sizes_reads_all_five(tmp_path):
    minds = str(tmp_path / "minds")
    _grow(minds, "architect", "design around the owner, never make them change")
    sizes = T.mind_sizes(minds)
    assert set(sizes) == {"principal", "analyst", "architect", "business_case", "skeptic"}
    assert sizes["architect"] == 1
    assert sizes["skeptic"] == 0
