"""
Wellness logging service.

Handles structured log entries (meals, mood, water, sleep, etc.)
and produces evidence signals for the cartographer.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from interviewer.storage import SoulStorage


VALID_ENTRY_KINDS = {
    "meal", "mood", "water", "sleep", "walk", "sunlight",
    "social", "weight", "purchase", "binge_marker", "note",
}

VALID_SOURCES = {"voice", "photo", "tap", "scan", "proactive", "manual"}


def log_entry(
    storage: SoulStorage,
    soul_id: int,
    kind: str,
    payload: dict,
    source: str = "manual",
    at: Optional[str] = None,
    confidence: float = 1.0,
) -> str:
    """Create and persist a wellness entry. Returns entry_id."""
    if kind not in VALID_ENTRY_KINDS:
        raise ValueError(f"Invalid entry kind: {kind}. Must be one of {VALID_ENTRY_KINDS}")
    if source not in VALID_SOURCES:
        raise ValueError(f"Invalid source: {source}. Must be one of {VALID_SOURCES}")

    entry_id = str(uuid.uuid4())
    at = at or datetime.now().isoformat()
    tagged_as_binge = 1 if kind == "binge_marker" else None

    storage.save_entry(
        soul_id=soul_id,
        entry_id=entry_id,
        kind=kind,
        payload=payload,
        at=at,
        source=source,
        confidence=confidence,
        tagged_as_binge=tagged_as_binge,
    )

    return entry_id


def entry_to_evidence(kind: str, payload: dict) -> List[Dict]:
    """Convert a logged entry into cartographer evidence signals."""
    signals = []

    if kind == "meal":
        signals.append({
            "dimension": "hunger_relationship",
            "signal": f"logged meal: {payload.get('name', 'unknown')}",
            "direction": 0.0,
            "confidence_delta": 0.04,
            "type": "demonstrated",
        })
        signals.append({
            "dimension": "food_preferences",
            "signal": f"ate {payload.get('name', 'unknown')}",
            "direction": 0.0,
            "confidence_delta": 0.03,
            "type": "demonstrated",
        })

    elif kind == "mood":
        reading = payload.get("reading", 0.5)
        signals.append({
            "dimension": "mood_baseline",
            "signal": f"mood reading: {reading}",
            "direction": reading - 0.5 if isinstance(reading, (int, float)) else 0.0,
            "confidence_delta": 0.05,
            "type": "demonstrated",
        })

    elif kind == "sleep":
        signals.append({
            "dimension": "sleep_pattern",
            "signal": f"slept {payload.get('duration_h', '?')}h",
            "direction": 0.0,
            "confidence_delta": 0.05,
            "type": "demonstrated",
        })

    elif kind in ("walk", "sunlight"):
        signals.append({
            "dimension": "movement_pattern",
            "signal": f"{kind}: {payload.get('duration_min', '?')} min",
            "direction": 0.0,
            "confidence_delta": 0.04,
            "type": "demonstrated",
        })

    elif kind == "social":
        signals.append({
            "dimension": "social_pattern",
            "signal": f"social: {payload.get('kind', 'interaction')}",
            "direction": 0.0,
            "confidence_delta": 0.04,
            "type": "demonstrated",
        })

    elif kind == "binge_marker":
        signals.append({
            "dimension": "hunger_relationship",
            "signal": "binge marker logged",
            "direction": -0.3,
            "confidence_delta": 0.06,
            "type": "demonstrated",
        })
        signals.append({
            "dimension": "risk_window_pattern",
            "signal": f"binge event",
            "direction": 0.0,
            "confidence_delta": 0.05,
            "type": "demonstrated",
        })

    elif kind == "water":
        signals.append({
            "dimension": "hunger_relationship",
            "signal": f"water: {payload.get('ml', '?')}ml",
            "direction": 0.0,
            "confidence_delta": 0.02,
            "type": "demonstrated",
        })

    return signals
