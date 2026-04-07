"""
Post-binge protocol middleware.

Sits between the WebSocket handler and VibSession.process_turn().
Reads post_binge_mode from CartographerState and constrains moves.

State transitions:
- binge_marker logged -> acute mode for 4 hours
- After 4h -> soft_morning mode until midnight + 24h
- After soft_morning expires -> cleared
"""

from typing import Set
from datetime import datetime, timedelta
from interviewer.models import MoveType, CartographerState


ACUTE_ALLOWED_MOVES = {
    MoveType.ACKNOWLEDGE,
    MoveType.VALIDATE,
    MoveType.REST,
    MoveType.GENTLE_OFFER,
}

SOFT_MORNING_BANNED_MOVES = {
    MoveType.PATTERN_CALLBACK,
}


def apply_post_binge_protocol(
    cartographer: CartographerState,
    eligible_moves: Set[MoveType],
) -> Set[MoveType]:
    """Constrain eligible moves based on post-binge mode."""
    if cartographer.post_binge_mode == "acute":
        return eligible_moves & ACUTE_ALLOWED_MOVES
    elif cartographer.post_binge_mode == "soft_morning":
        return eligible_moves - SOFT_MORNING_BANNED_MOVES
    return eligible_moves


def enter_acute_mode(cartographer: CartographerState):
    """Called when a binge_marker entry is logged."""
    cartographer.post_binge_mode = "acute"
    cartographer.post_binge_until = datetime.now() + timedelta(hours=4)


def check_mode_transition(cartographer: CartographerState):
    """Check if we should transition between post-binge modes."""
    if cartographer.post_binge_mode is None or cartographer.post_binge_until is None:
        return

    now = datetime.now()

    if cartographer.post_binge_mode == "acute" and now >= cartographer.post_binge_until:
        cartographer.post_binge_mode = "soft_morning"
        tomorrow_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cartographer.post_binge_until = tomorrow_midnight

    elif cartographer.post_binge_mode == "soft_morning" and now >= cartographer.post_binge_until:
        cartographer.post_binge_mode = None
        cartographer.post_binge_until = None
