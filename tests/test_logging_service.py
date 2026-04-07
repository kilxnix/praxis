import pytest
from vib_wellness.logging_service import log_entry, entry_to_evidence


def test_log_meal_entry(tmp_path):
    from interviewer.storage import SoulStorage
    db = SoulStorage(db_path=str(tmp_path / "test.db"))
    soul_id = db.get_or_create_soul("TestUser")

    entry_id = log_entry(
        storage=db,
        soul_id=soul_id,
        kind="meal",
        payload={"name": "chicken salad", "calories": 350},
    )

    assert entry_id is not None
    entries = db.load_entries(soul_id, kind="meal")
    assert len(entries) == 1
    assert entries[0]["payload"]["name"] == "chicken salad"
    db.close()


def test_invalid_kind_raises(tmp_path):
    from interviewer.storage import SoulStorage
    db = SoulStorage(db_path=str(tmp_path / "test.db"))
    soul_id = db.get_or_create_soul("TestUser")
    with pytest.raises(ValueError, match="Invalid entry kind"):
        log_entry(db, soul_id, kind="invalid_thing", payload={})
    db.close()


def test_meal_evidence_signals():
    signals = entry_to_evidence("meal", {"name": "pizza"})
    dims = [s["dimension"] for s in signals]
    assert "hunger_relationship" in dims
    assert "food_preferences" in dims


def test_binge_marker_evidence():
    signals = entry_to_evidence("binge_marker", {})
    dims = [s["dimension"] for s in signals]
    assert "hunger_relationship" in dims
    assert "risk_window_pattern" in dims
