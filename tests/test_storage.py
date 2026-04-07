"""Tests for soul persistence (SQLite storage)."""
import os
import tempfile
import pytest

from interviewer.storage import SoulStorage
from interviewer.orchestrator import VibSession
from interviewer.models import CartographerState, DimensionConfidence


@pytest.fixture
def storage():
    """Create a temporary storage instance that cleans up after itself."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = SoulStorage(db_path=path)
    yield s
    s.close()
    os.unlink(path)


class TestSoulLifecycle:
    def test_create_soul(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        assert soul_id > 0

    def test_get_existing_soul(self, storage):
        id1 = storage.get_or_create_soul("Alice")
        id2 = storage.get_or_create_soul("Alice")
        assert id1 == id2

    def test_different_names_different_ids(self, storage):
        id1 = storage.get_or_create_soul("Alice")
        id2 = storage.get_or_create_soul("Bob")
        assert id1 != id2

    def test_soul_exists(self, storage):
        assert storage.soul_exists("Alice") is False
        storage.get_or_create_soul("Alice")
        assert storage.soul_exists("Alice") is True


class TestSessions:
    def test_start_session(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, session_num = storage.start_session(soul_id)
        assert session_id > 0
        assert session_num == 1

    def test_session_numbers_increment(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        _, num1 = storage.start_session(soul_id)
        _, num2 = storage.start_session(soul_id)
        _, num3 = storage.start_session(soul_id)
        assert num1 == 1
        assert num2 == 2
        assert num3 == 3

    def test_session_count(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        assert storage.get_session_count(soul_id) == 0
        storage.start_session(soul_id)
        assert storage.get_session_count(soul_id) == 1
        storage.start_session(soul_id)
        assert storage.get_session_count(soul_id) == 2


class TestMessages:
    def test_save_and_load(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        storage.save_message(soul_id, session_id, 1, "user", "Hello there")
        storage.save_message(soul_id, session_id, 1, "assistant", "Hey, what's up?")

        msgs = storage.load_messages(soul_id)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello there"
        assert msgs[1]["role"] == "assistant"

    def test_load_respects_limit(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        for i in range(10):
            storage.save_message(soul_id, session_id, i, "user", f"msg {i}")

        msgs = storage.load_messages(soul_id, limit=3)
        assert len(msgs) == 3
        # Should be the most recent 3, in chronological order
        assert msgs[0]["content"] == "msg 7"
        assert msgs[2]["content"] == "msg 9"

    def test_messages_across_sessions(self, storage):
        soul_id = storage.get_or_create_soul("Alice")

        s1, _ = storage.start_session(soul_id)
        storage.save_message(soul_id, s1, 1, "user", "session 1 msg")

        s2, _ = storage.start_session(soul_id)
        storage.save_message(soul_id, s2, 1, "user", "session 2 msg")

        msgs = storage.load_messages(soul_id)
        assert len(msgs) == 2
        assert msgs[0]["content"] == "session 1 msg"
        assert msgs[1]["content"] == "session 2 msg"


class TestTraitEvidence:
    def test_save_and_load(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        signals = [
            {"dimension": "mood_baseline", "signal": "stable mood",
             "direction": 0.7, "confidence_delta": 0.05, "type": "demonstrated"},
            {"dimension": "social_pattern", "signal": "prefers small groups",
             "direction": -0.3, "confidence_delta": 0.04, "type": "stated"},
        ]
        storage.save_evidence(soul_id, session_id, 1, signals,
                              "I love exploring new cities but with close friends")

        evidence = storage.load_evidence(soul_id)
        assert len(evidence) == 2
        assert evidence[0]["dimension"] == "mood_baseline"
        assert evidence[0]["user_quote"] == "I love exploring new cities but with close friends"
        assert evidence[1]["dimension"] == "social_pattern"

    def test_invalid_dimensions_skipped(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        signals = [
            {"dimension": "made_up_dimension", "signal": "test",
             "direction": 0.5, "confidence_delta": 0.05, "type": "stated"},
            {"dimension": "mood_baseline", "signal": "real",
             "direction": 0.5, "confidence_delta": 0.05, "type": "stated"},
        ]
        storage.save_evidence(soul_id, session_id, 1, signals, "test quote")

        evidence = storage.load_evidence(soul_id)
        assert len(evidence) == 1
        assert evidence[0]["dimension"] == "mood_baseline"

    def test_load_by_dimension(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        signals = [
            {"dimension": "mood_baseline", "signal": "a", "direction": 0.5,
             "confidence_delta": 0.05, "type": "stated"},
            {"dimension": "mood_baseline", "signal": "b", "direction": 0.6,
             "confidence_delta": 0.04, "type": "demonstrated"},
            {"dimension": "social_pattern", "signal": "c", "direction": -0.3,
             "confidence_delta": 0.03, "type": "stated"},
        ]
        storage.save_evidence(soul_id, session_id, 1, signals, "test")

        by_dim = storage.load_evidence_by_dimension(soul_id)
        assert len(by_dim["mood_baseline"]) == 2
        assert len(by_dim["social_pattern"]) == 1


class TestContradictions:
    def test_save_and_load(self, storage):
        soul_id = storage.get_or_create_soul("Alice")

        storage.save_contradiction(soul_id, {
            "dimension": "social_pattern",
            "stated": "I'm outgoing",
            "demonstrated": "Avoids group topics",
            "confidence": 0.7,
            "first_noticed_session": 1,
        })

        contras = storage.load_contradictions(soul_id)
        assert len(contras) == 1
        assert contras[0].dimension == "social_pattern"
        assert contras[0].stated == "I'm outgoing"
        assert contras[0].explored is False

    def test_no_duplicate_contradictions(self, storage):
        soul_id = storage.get_or_create_soul("Alice")

        for _ in range(3):
            storage.save_contradiction(soul_id, {
                "dimension": "social_pattern",
                "stated": "I'm outgoing",
                "demonstrated": "Avoids group topics",
                "confidence": 0.7,
            })

        contras = storage.load_contradictions(soul_id)
        assert len(contras) == 1

    def test_mark_explored(self, storage):
        soul_id = storage.get_or_create_soul("Alice")

        storage.save_contradiction(soul_id, {
            "dimension": "social_pattern",
            "stated": "outgoing",
            "demonstrated": "avoids groups",
            "confidence": 0.7,
        })

        storage.mark_contradiction_explored(soul_id, "social_pattern")
        contras = storage.load_contradictions(soul_id)
        assert contras[0].explored is True


class TestSoulState:
    def test_default_state(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        state = storage.load_soul_state(soul_id)
        assert state["trust_score"] == 0.1
        assert state["phase"] == "FIRST_CONTACT"

    def test_save_and_load(self, storage):
        soul_id = storage.get_or_create_soul("Alice")

        storage.save_soul_state(soul_id, 0.65, "ATTUNED")
        state = storage.load_soul_state(soul_id)
        assert state["trust_score"] == 0.65
        assert state["phase"] == "ATTUNED"


class TestRebuildCartographer:
    def test_empty_soul(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        cart = storage.load_cartographer(soul_id)
        assert cart.mood_baseline.confidence == 0.0
        assert cart.mood_baseline.evidence_count == 0

    def test_rebuild_from_evidence(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        # Simulate multiple turns of evidence
        storage.save_evidence(soul_id, session_id, 1, [
            {"dimension": "mood_baseline", "signal": "stable",
             "direction": 0.7, "confidence_delta": 0.05, "type": "demonstrated"},
        ], "I love trying new things")

        storage.save_evidence(soul_id, session_id, 2, [
            {"dimension": "mood_baseline", "signal": "positive",
             "direction": 0.8, "confidence_delta": 0.06, "type": "demonstrated"},
        ], "Just booked a trip to Japan on a whim")

        cart = storage.load_cartographer(soul_id)
        assert cart.mood_baseline.confidence > 0
        assert cart.mood_baseline.evidence_count == 2
        assert cart.mood_baseline.stated_vs_demonstrated == "demonstrated"

    def test_rebuild_includes_contradictions(self, storage):
        soul_id = storage.get_or_create_soul("Alice")

        storage.save_contradiction(soul_id, {
            "dimension": "social_pattern",
            "stated": "outgoing",
            "demonstrated": "avoids groups",
            "confidence": 0.7,
        })

        cart = storage.load_cartographer(soul_id)
        assert len(cart.contradictions) == 1


class TestFullSoulLoad:
    def test_load_nonexistent(self, storage):
        result = storage.load_soul("Nobody")
        assert result is None

    def test_load_full_soul(self, storage):
        soul_id = storage.get_or_create_soul("Alice")
        session_id, _ = storage.start_session(soul_id)

        storage.save_message(soul_id, session_id, 1, "user", "Hello")
        storage.save_message(soul_id, session_id, 1, "assistant", "Hey")
        storage.save_evidence(soul_id, session_id, 1, [
            {"dimension": "mood_baseline", "signal": "test",
             "direction": 0.5, "confidence_delta": 0.05, "type": "stated"},
        ], "Hello")
        storage.save_soul_state(soul_id, 0.3, "DAILY_RHYTHM")

        soul = storage.load_soul("Alice")
        assert soul is not None
        assert soul["soul_id"] == soul_id
        assert len(soul["messages"]) == 2
        assert soul["trust_score"] == 0.3
        assert soul["phase"] == "DAILY_RHYTHM"
        assert soul["evidence_count"] == 1
        assert soul["cartographer"].mood_baseline.confidence > 0


class TestOrchestratorPersistence:
    """Test that VibSession actually persists through storage."""

    @pytest.mark.asyncio
    async def test_session_persists_messages(self, storage):
        session = VibSession(
            user_name="PersistUser", llm_client=None, storage=storage
        )
        await session.process_turn("I just moved to a new city")

        msgs = storage.load_messages(session.soul_id)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert "moved" in msgs[0]["content"]
        assert msgs[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_soul_survives_new_session(self, storage):
        """The whole point: create a session, talk, then create a NEW session
        and verify the soul state carried over."""
        # Session 1
        s1 = VibSession(
            user_name="SurviveUser", llm_client=None, storage=storage
        )
        await s1.process_turn("I love hiking in the mountains")
        await s1.process_turn("It makes me feel free")
        attunement_after_s1 = s1.graph.attunement_confidence

        # Session 2 -- same name, new VibSession
        s2 = VibSession(
            user_name="SurviveUser", llm_client=None, storage=storage
        )

        # Attunement should carry over
        assert s2.graph.attunement_confidence == pytest.approx(attunement_after_s1, abs=0.01)
        # Session number should increment
        assert s2.graph.session_number == 2
        # Conversation history from session 1 should be loaded
        assert len(s2.conversation_history) == 4  # 2 turns * 2 messages each

    @pytest.mark.asyncio
    async def test_attunement_persists(self, storage):
        s1 = VibSession(
            user_name="AttunementUser", llm_client=None, storage=storage
        )
        initial_attunement = s1.graph.attunement_confidence
        await s1.process_turn("Hello")

        state = storage.load_soul_state(s1.soul_id)
        assert state["trust_score"] > initial_attunement
