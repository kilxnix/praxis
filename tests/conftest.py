"""Shared test fixtures for Vib."""
import pytest
from interviewer.models import CartographerState, ConversationGraph


@pytest.fixture
def fresh_cartographer():
    """A blank cartographer state."""
    return CartographerState()


@pytest.fixture
def fresh_graph():
    """A blank conversation graph."""
    return ConversationGraph()
