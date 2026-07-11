from praxis.discovery_signals import (
    canonical_label, is_valid_step_label, is_vague,
)

def test_canonical_label_collapses_articles_case_punct():
    assert canonical_label("The Notebook!") == "notebook"
    assert canonical_label("my notebook") == "notebook"
    assert canonical_label("notebook") == "notebook"
    assert canonical_label("the order sheet") == "order sheet"

def test_is_valid_step_label():
    assert is_valid_step_label("take order") is True
    assert is_valid_step_label("match invoices to pos") is True         # 4 words
    assert is_valid_step_label("hoping someone ordered scones") is False # hedge
    assert is_valid_step_label("we just grab whatever looks edible now") is False  # >5 words
    assert is_valid_step_label("what do you file it in?") is False       # question
    assert is_valid_step_label("") is False


def test_is_valid_step_label_rejects_non_activities():
    # waits, pauses, passive states, and mistakes are not steps that move the work forward
    assert is_valid_step_label("wait by notebook") is False
    assert is_valid_step_label("wait for next call") is False
    assert is_valid_step_label("hang up") is False
    assert is_valid_step_label("mishear a model number") is False
    assert is_valid_step_label("remember the parts list") is False
    assert is_valid_step_label("cull images and edit") is True           # a real activity survives
    assert is_valid_step_label("take customer cash") is True


def test_is_valid_step_label_rejects_realtor_map_noise():
    """Exact non-steps from residential_realtor run — micro, umbrella, third-party."""
    assert is_valid_step_label("double-check phone after hanging up") is False
    assert is_valid_step_label("manage existing pipeline") is False
    assert is_valid_step_label("get properties listed") is False
    assert is_valid_step_label("delivers images") is False
    # Real owner activities from the same run still pass
    assert is_valid_step_label("pick best shots from photos") is True
    assert is_valid_step_label("write MLS description") is True
    assert is_valid_step_label("fill out DocuSign templates") is True
    assert is_valid_step_label("schedule showings on calls") is True

def test_is_vague():
    assert is_vague("uh, we do stuff") is True                 # <5 words
    assert is_vague("maybe we sort of handle it later somehow") is True  # hedge
    assert is_vague("I take the order in my notebook then bake") is False

def test_is_valid_step_label_word_boundary_no_hedge_confound():
    assert is_valid_step_label("bake bread and bag it") is True      # exactly 5 words, no hedge
    assert is_valid_step_label("take the order from the phone") is False  # 6 words, no hedge

def test_is_vague_word_boundary_and_empty():
    assert is_vague("") is True                          # empty -> vague
    assert is_vague("we take the order down") is False   # exactly 5 words, no hedge
    assert is_vague("we take order down") is True        # 4 words -> vague
