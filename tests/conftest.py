"""Shared test fixtures for Vib."""
import pytest
from interviewer.models import (
    ConversationGraph, CartographerState, Phase, EmotionalTemperature
)


@pytest.fixture
def fresh_graph():
    """A brand new conversation graph."""
    return ConversationGraph()


@pytest.fixture
def fresh_cartographer():
    """A blank cartographer state."""
    return CartographerState()
