"""Tests for the Soul Persona Builder — compiles a digital twin prompt."""
import pytest

from interviewer.persona_builder import build_soul_persona
from interviewer.models import (
    CartographerState, TraitConfidence, Contradiction, ConversationGraph
)


@pytest.fixture
def populated_cartographer():
    """A cartographer with some data collected."""
    c = CartographerState()
    c.openness = TraitConfidence(value=0.8, confidence=0.6, evidence_count=5)
    c.extroversion = TraitConfidence(value=0.3, confidence=0.5, evidence_count=3)
    c.communication_style = TraitConfidence(
        value=0.7, confidence=0.4, evidence_count=4,
        stated_vs_demonstrated="both"
    )
    c.vulnerability_comfort = TraitConfidence(value=0.4, confidence=0.3, evidence_count=2)
    c.contradictions.append(Contradiction(
        dimension="extroversion",
        stated="I'm pretty outgoing",
        demonstrated="Avoids group topics, prefers 1-on-1 scenarios",
        confidence=0.7,
    ))
    return c


@pytest.fixture
def sample_history():
    return [
        {"role": "assistant", "content": "What's been on your mind lately?"},
        {"role": "user", "content": "honestly I've been thinking about whether I should move. like, I love my friends here but the city feels small now."},
        {"role": "assistant", "content": "That tension between roots and restlessness... which side wins more often?"},
        {"role": "user", "content": "restlessness. always. I moved three times in my twenties. but I keep telling myself this time is different."},
    ]


class TestBuildSoulPersona:
    def test_returns_nonempty_string(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_includes_user_name(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "Alex" in prompt

    def test_includes_self_aware_framing(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "Soul" in prompt

    def test_includes_contradictions(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "outgoing" in prompt or "extroversion" in prompt

    def test_includes_speech_patterns(self, populated_cartographer, sample_history):
        prompt = build_soul_persona(
            name="Alex",
            cartographer=populated_cartographer,
            conversation_history=sample_history,
        )
        assert "speech" in prompt.lower() or "style" in prompt.lower()

    def test_works_with_minimal_data(self):
        prompt = build_soul_persona(
            name="NewUser",
            cartographer=CartographerState(),
            conversation_history=[],
        )
        assert isinstance(prompt, str)
        assert "NewUser" in prompt
        assert len(prompt) > 50
