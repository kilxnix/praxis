"""Verify the interviewer package imports work correctly."""


def test_models_import():
    from interviewer.models import (
        MoveType, Phase, EmotionalTemperature,
        CartographerState, ConversationGraph, DimensionConfidence,
        TraitConfidence,  # backward-compat alias
        Contradiction, CartographerNeeds, SelectedMove,
        OpenThread, MoveConstraints, MOVE_RULES,
    )
    assert len(MoveType) == 10
    assert len(Phase) == 4
    assert len(EmotionalTemperature) == 5
    # Backward compat alias
    assert TraitConfidence is DimensionConfidence


def test_orchestrator_import():
    from interviewer.orchestrator import VibSession


def test_move_generator_import():
    from interviewer.move_generator import (
        select_move, get_eligible_moves, is_move_eligible, score_move
    )


def test_prompt_builder_import():
    from interviewer.prompt_builder import build_prompt, validate_response


def test_llm_client_import():
    from interviewer.llm_client import OllamaLLMClient, ModelTier, SoulLLMClient


def test_persona_builder_import():
    from interviewer.persona_builder import build_soul_persona
