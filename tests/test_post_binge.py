from interviewer.models import MoveType, CartographerState
from vib_wellness.post_binge import (
    apply_post_binge_protocol,
    enter_acute_mode,
    check_mode_transition,
    ACUTE_ALLOWED_MOVES,
)


def test_acute_mode_restricts_moves():
    cart = CartographerState()
    enter_acute_mode(cart)
    assert cart.post_binge_mode == "acute"

    all_moves = set(MoveType)
    filtered = apply_post_binge_protocol(cart, all_moves)
    assert filtered == ACUTE_ALLOWED_MOVES
    assert MoveType.PATTERN_CALLBACK not in filtered
    assert MoveType.OBSERVATION not in filtered


def test_soft_morning_bans_pattern_callback():
    cart = CartographerState()
    cart.post_binge_mode = "soft_morning"

    all_moves = set(MoveType)
    filtered = apply_post_binge_protocol(cart, all_moves)
    assert MoveType.PATTERN_CALLBACK not in filtered
    assert MoveType.OBSERVATION in filtered


def test_no_binge_mode_passes_through():
    cart = CartographerState()
    all_moves = set(MoveType)
    filtered = apply_post_binge_protocol(cart, all_moves)
    assert filtered == all_moves
