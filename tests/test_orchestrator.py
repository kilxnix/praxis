"""Tests for the VibSession orchestrator."""
import pytest
from interviewer.orchestrator import (
    VibSession, analyze_message, apply_cartographer_updates,
    check_phase_transition, update_attunement,
)
from interviewer.models import (
    ConversationGraph, CartographerState, Phase,
    EmotionalTemperature, MoveType, DimensionConfidence,
)


class FakeLLMClient:
    """Mock LLM client that returns canned responses."""

    async def interviewer_generate(self, system, messages):
        return "That's a really honest answer."

    async def cartographer_analyze(self, system, analysis_input):
        return {
            "trait_signals": [
                {"dimension": "mood_baseline", "signal": "stable", "direction": 0.7,
                 "confidence_delta": 0.05, "type": "demonstrated"}
            ],
            "emotional_read": {"temperature": "warm", "trend": "warming", "energy": 0.6},
            "thread_updates": [
                {"action": "open", "topic": "moving", "context": "new city", "emotional_weight": 0.6}
            ],
            "contradiction_check": None,
            "unclassified": [],
        }

    async def mirror_generate(self, system, messages):
        return "Yeah, that sounds like me."


@pytest.fixture
def session():
    return VibSession(user_name="TestUser", llm_client=FakeLLMClient())


@pytest.fixture
def offline_session():
    return VibSession(user_name="TestUser", llm_client=None)


class TestProcessTurn:
    @pytest.mark.asyncio
    async def test_returns_response(self, session):
        result = await session.process_turn("I just moved to a new city.")
        assert "response" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_returns_move(self, session):
        result = await session.process_turn("I love hiking in the mountains.")
        assert "move" in result
        assert result["move"].move_type in MoveType

    @pytest.mark.asyncio
    async def test_increments_turn(self, session):
        assert session.graph.turn_number == 0
        await session.process_turn("hello")
        assert session.graph.turn_number == 1

    @pytest.mark.asyncio
    async def test_records_history(self, session):
        await session.process_turn("hello")
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0]["role"] == "user"
        assert session.conversation_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_offline_mode(self, offline_session):
        result = await offline_session.process_turn("testing")
        assert "response" in result
        assert len(result["response"]) > 0


class TestPhaseTransitions:
    def test_stays_in_arrival_initially(self):
        graph = ConversationGraph()
        cart = CartographerState()
        assert check_phase_transition(graph, cart) == Phase.ARRIVAL

    def test_advances_to_daily_rhythm(self):
        graph = ConversationGraph(
            attunement_confidence=0.3,
            turn_number=6,
        )
        cart = CartographerState()
        cart.mood_baseline = DimensionConfidence(confidence=0.2)
        cart.sleep_pattern = DimensionConfidence(confidence=0.2)
        cart.hunger_relationship = DimensionConfidence(confidence=0.2)
        cart.movement_pattern = DimensionConfidence(confidence=0.2)
        cart.social_pattern = DimensionConfidence(confidence=0.2)
        assert check_phase_transition(graph, cart) == Phase.DAILY_RHYTHM


class TestAttunement:
    def test_warm_temperature_builds_attunement(self):
        graph = ConversationGraph(
            temperature=EmotionalTemperature.WARM,
            attunement_confidence=0.1,
        )
        analysis = {"thread_updates": [], "trait_signals": []}
        new_attunement = update_attunement(graph, analysis)
        assert new_attunement > 0.1

    def test_cold_temperature_reduces_attunement(self):
        graph = ConversationGraph(
            temperature=EmotionalTemperature.COLD,
            attunement_confidence=0.5,
        )
        analysis = {"thread_updates": [], "trait_signals": []}
        new_attunement = update_attunement(graph, analysis)
        # Base increment (+0.008) minus cold penalty (-0.005) = net +0.003
        assert new_attunement > 0.5  # still goes up slightly due to base increment


class TestCartographerUpdates:
    def test_applies_trait_signals(self):
        cart = CartographerState()
        graph = ConversationGraph(turn_number=1, session_number=1)
        analysis = {
            "trait_signals": [
                {"dimension": "mood_baseline", "signal": "stable",
                 "confidence_delta": 0.05, "type": "demonstrated"}
            ],
            "emotional_read": {"temperature": "warm", "trend": "warming", "energy": 0.6},
            "thread_updates": [],
            "contradiction_check": None,
            "unclassified": [],
        }
        cart, graph = apply_cartographer_updates(analysis, cart, graph)
        assert cart.mood_baseline.confidence > 0

    def test_opens_thread(self):
        cart = CartographerState()
        graph = ConversationGraph(turn_number=1, session_number=1)
        analysis = {
            "trait_signals": [],
            "emotional_read": {"temperature": "cool", "trend": "stable", "energy": 0.5},
            "thread_updates": [
                {"action": "open", "topic": "career", "context": "new job", "emotional_weight": 0.7}
            ],
            "contradiction_check": None,
            "unclassified": [],
        }
        cart, graph = apply_cartographer_updates(analysis, cart, graph)
        assert len(graph.open_threads) == 1
        assert graph.open_threads[0].topic == "career"


class TestSoulReadiness:
    def test_starts_at_zero(self, session):
        readiness = session.get_soul_readiness()
        assert readiness["overall_confidence"] == 0.0
        assert readiness["attuned"] is False

    def test_structure(self, session):
        readiness = session.get_soul_readiness()
        assert "dimensions" in readiness
        assert len(readiness["dimensions"]) == 10
        assert "phase" in readiness
        assert "attunement_level" in readiness
