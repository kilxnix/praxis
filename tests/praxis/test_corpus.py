"""The generated training corpus: shape, uniqueness, no collision with the built-ins, and that
each business carries a real workflow with a volume/time signal on its core work — so training on
it actually exercises the firm's core-work reasoning rather than thin stubs."""
from praxis.eval.scenarios import Scenario, SCENARIOS
from praxis.eval.corpus import CORPUS
from praxis.train import business_pool


def test_corpus_is_scenarios():
    assert len(CORPUS) >= 20
    assert all(isinstance(s, Scenario) for s in CORPUS)


def test_fields_present_and_substantial():
    for s in CORPUS:
        assert s.key and s.business and s.persona and s.truth
        assert len(s.truth) > 200          # a real end-to-end workflow, not a stub


def test_keys_unique_and_no_collision_with_builtins():
    keys = [s.key for s in CORPUS]
    assert len(keys) == len(set(keys))
    builtin = {s.key for s in SCENARIOS}
    assert builtin.isdisjoint(keys)        # corpus never shadows a built-in scenario


def test_each_truth_has_a_volume_or_time_marker():
    # every generated business was required to put a concrete count/duration on its core work
    for s in CORPUS:
        assert any(ch.isdigit() for ch in s.truth), s.key


def test_pool_includes_corpus_and_builtins():
    pool = business_pool()
    keys = {s.key for s in pool}
    assert keys >= {s.key for s in CORPUS}
    assert keys >= {s.key for s in SCENARIOS}
    assert len(pool) == len(SCENARIOS) + len(CORPUS)
