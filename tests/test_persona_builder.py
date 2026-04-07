"""Tests for the Soul Persona Builder."""
import pytest

from interviewer.persona_builder import build_soul_persona
from interviewer.models import CartographerState, DimensionConfidence, Contradiction


@pytest.fixture
def populated_cartographer():
    """A cartographer with some data collected."""
    c = CartographerState()
    c.mood_baseline = DimensionConfidence(value=0.8, confidence=0.6, evidence_count=5)
    c.social_pattern = DimensionConfidence(value=0.3, confidence=0.5, evidence_count=3)
    c.response_style = DimensionConfidence(
        value=0.7, confidence=0.4, evidence_count=4,
        stated_vs_demonstrated="both"
    )
    c.mood_volatility = DimensionConfidence(value=0.4, confidence=0.3, evidence_count=2)
    c.contradictions.append(Contradiction(
        dimension="social_pattern",
        stated="I'm pretty outgoing",
        demonstrated="Avoids group topics, prefers 1-on-1 scenarios",
        confidence=0.7,
    ))
    return c


@pytest.fixture
def sample_history():
    return [
        {"role": "user", "content": "honestly I've been thinking about whether I should move."},
        {"role": "assistant", "content": "What's pulling you in that direction?"},
        {"role": "user", "content": "maybe somewhere new, idk..."},
    ]


class TestBuildSoulPersona:
    def test_returns_string(self, populated_cartographer, sample_history):
        prompt = build_soul_persona("Alex", populated_cartographer, sample_history)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_includes_name(self, populated_cartographer, sample_history):
        prompt = build_soul_persona("Alex", populated_cartographer, sample_history)
        assert "Alex" in prompt

    def test_includes_contradictions(self, populated_cartographer, sample_history):
        prompt = build_soul_persona("Alex", populated_cartographer, sample_history)
        assert "outgoing" in prompt or "social_pattern" in prompt

    def test_includes_communication_style(self, populated_cartographer, sample_history):
        prompt = build_soul_persona("Alex", populated_cartographer, sample_history)
        assert "style" in prompt.lower() or "communication" in prompt.lower()

    def test_works_with_minimal_data(self):
        prompt = build_soul_persona("NewUser", CartographerState(), [])
        assert isinstance(prompt, str)
        assert "NewUser" in prompt

    def test_includes_rules(self, populated_cartographer, sample_history):
        prompt = build_soul_persona("Alex", populated_cartographer, sample_history)
        assert "RULES" in prompt
        assert "Soul" in prompt or "Vib" in prompt
