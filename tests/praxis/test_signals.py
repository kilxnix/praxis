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

def test_is_vague():
    assert is_vague("uh, we do stuff") is True                 # <5 words
    assert is_vague("maybe we sort of handle it later somehow") is True  # hedge
    assert is_vague("I take the order in my notebook then bake") is False
