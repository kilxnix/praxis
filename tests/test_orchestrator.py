"""Tests for the async InterviewerSession orchestrator."""
import pytest
from interviewer.orchestrator import InterviewerSession
from interviewer.models import Phase, MoveType


class FakeLLMClient:
    """Mock LLM client that returns canned responses."""

    async def interviewer_generate(self, system, messages):
        return "That sounds like it really matters to you."

    async def cartographer_analyze(self, system, analysis_input):
        return {
            "trait_signals": [],
            "emotional_read": {
                "temperature": "warm",
                "trend": "warming",
                "energy": 0.6,
            },
            "thread_updates": [],
            "contradiction_check": None,
            "unclassified": [],
        }


@pytest.fixture
def session():
    return InterviewerSession(user_name="TestUser", llm_client=FakeLLMClient())


@pytest.fixture
def offline_session():
    return InterviewerSession(user_name="TestUser", llm_client=None)


class TestProcessTurn:
    @pytest.mark.asyncio
    async def test_returns_response(self, session):
        result = await session.process_turn("I just moved to a new city")
        assert "response" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_increments_turn_number(self, session):
        assert session.graph.turn_number == 0
        await session.process_turn("Hello")
        assert session.graph.turn_number == 1
        await session.process_turn("How are you")
        assert session.graph.turn_number == 2

    @pytest.mark.asyncio
    async def test_records_conversation_history(self, session):
        await session.process_turn("Test message")
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0]["role"] == "user"
        assert session.conversation_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_returns_move_info(self, session):
        result = await session.process_turn("I love hiking")
        assert "move" in result
        assert hasattr(result["move"], "move_type")

    @pytest.mark.asyncio
    async def test_offline_mode_works(self, offline_session):
        result = await offline_session.process_turn("Hello there")
        assert "response" in result
        assert result["response"]


class TestSoulReadiness:
    def test_readiness_report_structure(self, session):
        report = session.get_soul_readiness()
        assert "overall_confidence" in report
        assert "matchable" in report
        assert "dimensions" in report
        assert len(report["dimensions"]) == 10

    def test_starts_not_matchable(self, session):
        report = session.get_soul_readiness()
        assert report["matchable"] is False


class TestNewSession:
    @pytest.mark.asyncio
    async def test_increments_session_number(self, session):
        assert session.graph.session_number == 1
        session.start_new_session()
        assert session.graph.session_number == 2

    @pytest.mark.asyncio
    async def test_resets_turn_number(self, session):
        await session.process_turn("Hello")
        assert session.graph.turn_number == 1
        session.start_new_session()
        assert session.graph.turn_number == 0
