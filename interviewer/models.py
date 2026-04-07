"""
The Soul — Interviewer Internal Models
These define the state objects that the three systems (Graph, Cartographer, Move Generator)
use to communicate with each other.

Using dataclasses for zero-dependency operation.
Swap to Pydantic for production (validation, serialization).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
from datetime import datetime


# ─────────────────────────────────────────────
# MOVE TYPES
# ─────────────────────────────────────────────

class MoveType(str, Enum):
    OPEN_DOOR = "open_door"
    FOLLOW_THREAD = "follow_thread"
    OBSERVATION = "observation"
    HYPOTHETICAL = "hypothetical"
    GENTLE_CONTRADICTION = "gentle_contradiction"
    CALLBACK = "callback"
    SHARE = "share"
    REST = "rest"


@dataclass
class MoveConstraints:
    """Rules governing when a move type is allowed."""
    min_phase: int = 1
    min_trust_score: float = 0.0
    requires_open_threads: bool = False
    requires_contradiction: bool = False
    requires_prior_sessions: bool = False
    max_frequency_per_session: Optional[int] = None
    cooldown_turns: int = 0


MOVE_RULES: Dict[MoveType, MoveConstraints] = {
    MoveType.OPEN_DOOR: MoveConstraints(
        min_phase=1,
        max_frequency_per_session=4,
    ),
    MoveType.FOLLOW_THREAD: MoveConstraints(
        min_phase=1,
        requires_open_threads=True,
    ),
    MoveType.OBSERVATION: MoveConstraints(
        min_phase=1,
        min_trust_score=0.15,
        cooldown_turns=3,
    ),
    MoveType.HYPOTHETICAL: MoveConstraints(
        min_phase=1,
        max_frequency_per_session=3,
        cooldown_turns=2,
    ),
    MoveType.GENTLE_CONTRADICTION: MoveConstraints(
        min_phase=2,
        min_trust_score=0.4,
        requires_contradiction=True,
        max_frequency_per_session=1,
        cooldown_turns=5,
    ),
    MoveType.CALLBACK: MoveConstraints(
        min_phase=1,
        max_frequency_per_session=2,
        cooldown_turns=4,
    ),
    MoveType.SHARE: MoveConstraints(
        min_phase=1,
        min_trust_score=0.1,
        max_frequency_per_session=3,
        cooldown_turns=3,
    ),
    MoveType.REST: MoveConstraints(
        min_phase=1,
    ),
}


# ─────────────────────────────────────────────
# CONVERSATION GRAPH STATE
# ─────────────────────────────────────────────

class EmotionalTemperature(str, Enum):
    COLD = "cold"
    COOL = "cool"
    WARM = "warm"
    HOT = "hot"
    VOLATILE = "volatile"


class Phase(int, Enum):
    ARRIVAL = 1
    DAILY_RHYTHM = 2
    ATTUNED = 3
    COMPANION = 4


PHASE_ALIASES = {
    "FIRST_CONTACT": Phase.ARRIVAL,
    "PATTERN_RECOGNITION": Phase.DAILY_RHYTHM,
    "DEPTH": Phase.ATTUNED,
    "ONGOING": Phase.COMPANION,
    "ARRIVAL": Phase.ARRIVAL,
    "DAILY_RHYTHM": Phase.DAILY_RHYTHM,
    "ATTUNED": Phase.ATTUNED,
    "COMPANION": Phase.COMPANION,
}

def phase_from_str(s: str) -> Phase:
    """Resolve a phase string, handling old dating-Vib names."""
    return PHASE_ALIASES.get(s.upper(), Phase.ARRIVAL)


@dataclass
class OpenThread:
    """Something the user mentioned but didn't finish."""
    topic: str
    context: str
    emotional_weight: float = 0.5
    times_referenced: int = 1
    deliberately_tabled: bool = False
    session_originated: int = 0
    last_referenced_turn: int = 0


@dataclass
class ConversationGraph:
    """System 1: Where are we right now in the dialogue?"""
    session_number: int = 1
    turn_number: int = 0
    phase: Phase = Phase.ARRIVAL
    attunement_confidence: float = 0.1

    temperature: EmotionalTemperature = EmotionalTemperature.COOL
    temperature_trend: str = "stable"
    energy_level: float = 0.5

    open_threads: List[OpenThread] = field(default_factory=list)
    current_thread: Optional[str] = None

    move_history: List[Tuple[int, MoveType]] = field(default_factory=list)

    session_start: Optional[datetime] = None
    last_heavy_moment_turn: Optional[int] = None


# ─────────────────────────────────────────────
# CARTOGRAPHER STATE
# ─────────────────────────────────────────────

@dataclass
class DimensionConfidence:
    """A single dimension measurement with confidence tracking."""
    value: Optional[float] = None
    confidence: float = 0.0
    evidence_count: int = 0
    last_updated_session: int = 0
    stated_vs_demonstrated: Optional[str] = None

# Backward compat alias
TraitConfidence = DimensionConfidence


@dataclass
class Contradiction:
    """A gap between what the user says and what their behavior shows."""
    dimension: str
    stated: str
    demonstrated: str
    confidence: float
    first_noticed_session: int = 0
    explored: bool = False


@dataclass
class CartographerNeeds:
    """What the Cartographer is hungry for."""
    dimension: str
    current_confidence: float
    priority: float
    suggested_approach: Optional[str] = None


@dataclass
class CartographerState:
    """System 2: What do we know about this user's wellness state?"""
    mood_baseline: DimensionConfidence = field(default_factory=DimensionConfidence)
    mood_volatility: DimensionConfidence = field(default_factory=DimensionConfidence)
    sleep_pattern: DimensionConfidence = field(default_factory=DimensionConfidence)
    hunger_relationship: DimensionConfidence = field(default_factory=DimensionConfidence)
    food_preferences: DimensionConfidence = field(default_factory=DimensionConfidence)
    risk_window_pattern: DimensionConfidence = field(default_factory=DimensionConfidence)
    movement_pattern: DimensionConfidence = field(default_factory=DimensionConfidence)
    social_pattern: DimensionConfidence = field(default_factory=DimensionConfidence)
    stressor_signals: DimensionConfidence = field(default_factory=DimensionConfidence)
    response_style: DimensionConfidence = field(default_factory=DimensionConfidence)

    # Post-binge protocol state
    post_binge_mode: Optional[str] = None   # None | "acute" | "soft_morning"
    post_binge_until: Optional[datetime] = None

    contradictions: List[Contradiction] = field(default_factory=list)
    needs: List[CartographerNeeds] = field(default_factory=list)
    unclassified_signals: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# MOVE GENERATOR OUTPUT
# ─────────────────────────────────────────────

@dataclass
class SelectedMove:
    """The Move Generator's decision."""
    move_type: MoveType
    reasoning: str
    target_dimension: Optional[str] = None
    thread_reference: Optional[str] = None
    contradiction_reference: Optional[str] = None
    prompt_context: str = ""
