"""Verify the package restructure didn't break anything."""


def test_models_import():
    from interviewer.models import (
        Phase, MoveType, EmotionalTemperature,
        ConversationGraph, CartographerState, SelectedMove,
        MOVE_RULES,
    )
    assert len(MOVE_RULES) == 8


def test_move_generator_import():
    from interviewer.move_generator import select_move, get_eligible_moves


def test_prompt_builder_import():
    from interviewer.prompt_builder import build_prompt, validate_response


def test_orchestrator_import():
    from interviewer.orchestrator import InterviewerSession


def test_package_init_import():
    from interviewer import InterviewerSession, Phase, MoveType
