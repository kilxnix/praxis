# Wellness Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition the Vib codebase from an agentic dating app to a wellness companion by deleting the dating-specific packages (`vib/`, `world/`), renaming concepts, swapping the 10 personality dimensions for 10 wellness state dimensions, remapping the 8 moves to 10 wellness moves, rewriting the base persona, adding wellness storage tables, a vision model tier, a new `vib_wellness/` services package, logging endpoints, and a post-binge protocol middleware.

**Architecture:** The existing three-system interviewer design (Conversation Graph + Cartographer + Move Generator) stays intact -- it's structurally the attunement layer. The Cartographer's dimensions change from personality traits to wellness state dimensions. Two new moves are added (`acknowledge`, `state_check`). A new `vib_wellness/` package adds logging, vision, nudge, and post-binge services. Server gains structured log message handlers and a photo upload HTTP endpoint.

**Tech Stack:** Python 3.8+, FastAPI, Ollama (qwen3.5:9b + qwen2.5-vl:7b for vision), SQLite (WAL), vanilla JS frontend, pytest + pytest-asyncio.

**Source spec:** `Wellness Upgrade/wellness-pivot-plan.md` and `Wellness Upgrade/001_add_wellness_tables.sql`

---

## File Structure

### Files to DELETE
```
vib/__init__.py
vib/models.py
vib/orchestrator.py
vib/evaluator.py
vib/prompts.py
world/__init__.py
world/models.py
world/orchestrator.py
world/encounter.py
world/routine.py
world/locations.py
world/reporter.py
world/spatial/types.py
world/spatial/movement.py
world/spatial/proximity.py
world/spatial/simulation.py
world/spatial/town.py
world/spatial/__init__.py
tests/test_world.py
tests/test_world_gen.py
tests/test_spatial_types.py
tests/test_spatial_movement.py
tests/test_spatial_proximity.py
tests/test_spatial_simulation.py
tests/test_spatial_integration.py
tests/test_spatial_town.py
tests/test_exploration.py
tests/test_autonomy.py
tests/test_action_engine.py
```

### Files to MODIFY
```
interviewer/__init__.py          -- Update exports (InterviewerSession -> VibSession)
interviewer/models.py            -- New Phase names, new MoveType enum, new CartographerState dimensions, post_binge fields
interviewer/orchestrator.py      -- Rename class, new dimensions, insert post-binge middleware + log side-channel
interviewer/move_generator.py    -- New move set, new eligibility rules, new scoring, new context builders
interviewer/prompt_builder.py    -- New base persona, new phase prompts, new move guides, wellness metadata
interviewer/llm_client.py        -- Add VISION tier
interviewer/persona_builder.py   -- Remove "vib" context, rename "mirror" -> "companion_voice"
interviewer/storage.py           -- Add wellness tables, entry CRUD, remove vib session methods
server.py                        -- Remove dating handlers, add log_* handlers, add /upload/photo
static/index.html                -- Remove world screen, update labels
static/app.js                    -- Remove world/vib handlers, update phase labels, add log handlers
static/style.css                 -- Update aesthetic (optional, low priority)
requirements.txt                 -- Add python-multipart
tests/conftest.py                -- Update fixtures for new dimensions
tests/test_imports.py            -- Update for new exports
tests/test_orchestrator.py       -- Update for VibSession + new dimensions
tests/test_server.py             -- Update for new message types
tests/test_llm_client.py         -- Add vision tier test
tests/test_persona_builder.py    -- Update for companion_voice context
tests/test_storage.py            -- Add wellness table tests
demo.py                          -- Update for wellness conversation
```

### Files to CREATE
```
vib_wellness/__init__.py
vib_wellness/logging_service.py  -- Entry creation, validation, acknowledgment
vib_wellness/vision_service.py   -- Photo -> macros via vision model
vib_wellness/post_binge.py       -- Post-binge protocol middleware
vib_wellness/state_computer.py   -- Compute VibState from entries
migrations/001_add_wellness_tables.sql  -- (copy from Wellness Upgrade/)
tests/test_logging_service.py
tests/test_post_binge.py
tests/test_vision_service.py
```

---

### Task 1: Create branch and delete dead packages

**Files:**
- Delete: `vib/`, `world/`, dead test files
- Modify: `.gitignore` (no changes needed)

- [ ] **Step 1: Create the wellness-pivot branch**

```bash
cd "C:/Users/whate/Documents/AI Locally/Vib - Agentic Dating"
git checkout -b wellness-pivot
git tag pre-pivot-snapshot
```

- [ ] **Step 2: Delete the `vib/` package**

```bash
rm -rf vib/
```

- [ ] **Step 3: Delete the `world/` package**

```bash
rm -rf world/
```

- [ ] **Step 4: Delete dead test files**

```bash
rm -f tests/test_world.py tests/test_world_gen.py
rm -f tests/test_spatial_types.py tests/test_spatial_movement.py
rm -f tests/test_spatial_proximity.py tests/test_spatial_simulation.py
rm -f tests/test_spatial_integration.py tests/test_spatial_town.py
rm -f tests/test_exploration.py tests/test_autonomy.py tests/test_action_engine.py
```

- [ ] **Step 5: Commit the deletions**

```bash
git add -A
git commit -m "chore: delete vib/ and world/ packages for wellness pivot"
```

---

### Task 2: Rename Phase enum, class names, and trust_score

**Files:**
- Modify: `interviewer/models.py`
- Modify: `interviewer/__init__.py`
- Modify: `interviewer/orchestrator.py`
- Modify: `interviewer/storage.py`
- Test: `tests/test_imports.py`

- [ ] **Step 1: Update Phase enum in `interviewer/models.py`**

Replace the Phase enum:

```python
class Phase(int, Enum):
    ARRIVAL = 1            # was FIRST_CONTACT
    DAILY_RHYTHM = 2       # was PATTERN_RECOGNITION
    ATTUNED = 3            # was DEPTH
    COMPANION = 4          # was ONGOING
```

- [ ] **Step 2: Add phase aliases for backward compatibility on load**

In `interviewer/models.py`, add a helper after the Phase enum:

```python
# Backward-compatible phase lookup (old DB values -> new enum)
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
```

- [ ] **Step 3: Rename `InterviewerSession` to `VibSession` in `interviewer/orchestrator.py`**

Change the class definition line and all internal self-references. Also rename `trust_score` to `attunement_confidence` on `ConversationGraph` in `interviewer/models.py`:

In `interviewer/models.py`, in the `ConversationGraph` dataclass:
```python
    attunement_confidence: float = 0.1   # was trust_score
```

Search-and-replace `trust_score` -> `attunement_confidence` across:
- `interviewer/models.py` (the field)
- `interviewer/orchestrator.py` (all references: `graph.trust_score` -> `graph.attunement_confidence`, function params, etc.)
- `interviewer/move_generator.py` (eligibility checks reference `graph.trust_score`)
- `interviewer/prompt_builder.py` (metadata block references trust)
- `interviewer/storage.py` (save_soul_state, load_soul_state -- keep DB column name `trust_score` for migration simplicity, just map in Python)

- [ ] **Step 4: Update `interviewer/__init__.py`**

```python
from interviewer.models import (
    Phase, MoveType, EmotionalTemperature,
    ConversationGraph, CartographerState, SelectedMove,
)
from interviewer.orchestrator import VibSession
```

- [ ] **Step 5: Update storage.py phase handling**

In `storage.py`, use `phase_from_str()` when loading soul state:

```python
from interviewer.models import (
    CartographerState, TraitConfidence, Contradiction, CartographerNeeds,
    ConversationGraph, Phase, EmotionalTemperature, phase_from_str,
)
```

In `load_soul_state`, the `phase` value returned is a string that the orchestrator passes to `Phase[state["phase"]]`. Update the orchestrator to use `phase_from_str(state["phase"])` instead.

- [ ] **Step 6: Update `server.py` imports**

Change `from interviewer.orchestrator import InterviewerSession` to `from interviewer.orchestrator import VibSession`. Update all usages of `InterviewerSession` in server.py to `VibSession`.

- [ ] **Step 7: Update all Phase references in orchestrator.py**

Replace all `Phase.FIRST_CONTACT` with `Phase.ARRIVAL`, `Phase.PATTERN_RECOGNITION` with `Phase.DAILY_RHYTHM`, `Phase.DEPTH` with `Phase.ATTUNED`, `Phase.ONGOING` with `Phase.COMPANION`.

- [ ] **Step 8: Update all Phase references in move_generator.py and prompt_builder.py**

Same replacements in both files.

- [ ] **Step 9: Run tests to verify renames didn't break anything**

```bash
.venv/Scripts/python.exe -m pytest tests/test_imports.py tests/test_orchestrator.py -v
```

Expected: Some failures from missing vib/world imports in test files, but core interviewer tests should pass with the renames.

- [ ] **Step 10: Commit**

```bash
git add interviewer/ server.py tests/
git commit -m "refactor: rename phases, InterviewerSession->VibSession, trust_score->attunement_confidence"
```

---

### Task 3: Rewrite CartographerState with 10 wellness dimensions

**Files:**
- Modify: `interviewer/models.py`
- Modify: `interviewer/orchestrator.py` (cartographer system prompt + dimension aliases + needs computation)
- Modify: `interviewer/storage.py` (DIMENSIONS list)
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Replace CartographerState dimensions in `interviewer/models.py`**

Replace the 10 personality dimension fields with 10 wellness dimensions. Keep `TraitConfidence` (rename to `DimensionConfidence` is optional -- do it). Keep `Contradiction`, `CartographerNeeds`.

```python
@dataclass
class DimensionConfidence:
    """A single dimension measurement with confidence tracking."""
    value: Optional[float] = None
    confidence: float = 0.0
    evidence_count: int = 0
    last_updated_session: int = 0
    stated_vs_demonstrated: Optional[str] = None


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
```

Keep `TraitConfidence` as a backward-compatible alias:
```python
TraitConfidence = DimensionConfidence  # backward compat
```

- [ ] **Step 2: Update DIMENSIONS list in `interviewer/storage.py`**

```python
DIMENSIONS = [
    "mood_baseline", "mood_volatility", "sleep_pattern",
    "hunger_relationship", "food_preferences", "risk_window_pattern",
    "movement_pattern", "social_pattern", "stressor_signals",
    "response_style",
]
```

- [ ] **Step 3: Update CARTOGRAPHER_SYSTEM_PROMPT in `interviewer/orchestrator.py`**

Replace the personality-focused prompt with a wellness-focused one:

```python
CARTOGRAPHER_SYSTEM_PROMPT = """You are the Vib Cartographer. You analyze user messages and map wellness state.

VALID DIMENSIONS (use ONLY these exact strings):
- mood_baseline
- mood_volatility
- sleep_pattern
- hunger_relationship
- food_preferences
- risk_window_pattern
- movement_pattern
- social_pattern
- stressor_signals
- response_style

Return JSON with this EXACT structure:
{
  "trait_signals": [
    {"dimension": "<one of the 10 above>", "signal": "<what you observed>", "direction": <-1.0 to 1.0>, "confidence_delta": <0.01 to 0.08>, "type": "stated"|"demonstrated"}
  ],
  "emotional_read": {"temperature": "cold"|"cool"|"warm"|"hot", "trend": "warming"|"cooling"|"stable", "energy": <0.0 to 1.0>},
  "thread_updates": [
    {"action": "open"|"continue"|"close"|"deflect", "topic": "<short label>", "context": "<brief>", "emotional_weight": <0.0 to 1.0>}
  ],
  "contradiction_check": null,
  "unclassified": []
}

RULES:
- Map messages to wellness dimensions. Mood references -> mood_baseline/mood_volatility. Food mentions -> hunger_relationship/food_preferences. Sleep mentions -> sleep_pattern. Activity -> movement_pattern. Social mentions -> social_pattern.
- "demonstrated" = behavior implies it (worth more). "stated" = they said it directly.
- confidence_delta: 0.03-0.05 for mild signals, 0.06-0.08 for strong signals.
- thread_updates MUST be an array, even if only one item.
- Do NOT invent dimensions. Only use the 10 listed above.
- Return ONLY valid JSON, no markdown fences."""
```

- [ ] **Step 4: Update `_DIMENSION_ALIASES` in orchestrator.py**

```python
_DIMENSION_ALIASES = {
    "mood": "mood_baseline",
    "sleep": "sleep_pattern",
    "hunger": "hunger_relationship",
    "food": "food_preferences",
    "risk": "risk_window_pattern",
    "movement": "movement_pattern",
    "exercise": "movement_pattern",
    "social": "social_pattern",
    "stress": "stressor_signals",
    "stressors": "stressor_signals",
    "style": "response_style",
    "communication": "response_style",
    # Old personality dims -> map to closest wellness equivalent
    "openness": "mood_baseline",
    "conscientiousness": "sleep_pattern",
    "extroversion": "social_pattern",
    "agreeableness": "response_style",
    "neuroticism": "mood_volatility",
    "attachment_style": "hunger_relationship",
    "conflict_style": "stressor_signals",
    "communication_style": "response_style",
    "vulnerability_comfort": "mood_baseline",
    "independence_interdependence": "social_pattern",
}
```

- [ ] **Step 5: Update `_compute_needs()` in orchestrator.py**

Replace the matching_importance dict with wellness dimension priorities:

```python
def _compute_needs(cartographer: CartographerState, graph: ConversationGraph) -> List[CartographerNeeds]:
    needs = []
    wellness_importance = {
        "mood_baseline": 0.95,
        "hunger_relationship": 0.9,
        "sleep_pattern": 0.85,
        "mood_volatility": 0.8,
        "risk_window_pattern": 0.8,
        "movement_pattern": 0.7,
        "social_pattern": 0.7,
        "food_preferences": 0.6,
        "stressor_signals": 0.6,
        "response_style": 0.55,
    }

    for dimension, importance in wellness_importance.items():
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, DimensionConfidence):
            if tc.confidence < 0.7:
                priority = importance * (1.0 - tc.confidence)
                if dimension in ("risk_window_pattern", "stressor_signals"):
                    if graph.phase.value < Phase.ATTUNED.value:
                        priority *= 0.4
                needs.append(CartographerNeeds(
                    dimension=dimension,
                    current_confidence=tc.confidence,
                    priority=round(priority, 3),
                ))

    needs.sort(key=lambda n: n.priority, reverse=True)
    return needs
```

- [ ] **Step 6: Update `check_phase_transition()` in orchestrator.py**

```python
def check_phase_transition(graph: ConversationGraph, cartographer: CartographerState) -> Phase:
    current = graph.phase

    if current == Phase.ARRIVAL:
        # -> DAILY_RHYTHM: attunement building, some data collected
        basic_measured = sum(
            1 for dim in ["mood_baseline", "sleep_pattern", "hunger_relationship", "movement_pattern", "social_pattern"]
            if getattr(cartographer, dim).confidence > 0.15
        )
        if graph.attunement_confidence > 0.2 and graph.turn_number >= 5 and basic_measured >= 3:
            return Phase.DAILY_RHYTHM

    elif current == Phase.DAILY_RHYTHM:
        # -> ATTUNED: enough data to spot patterns
        observations_made = sum(
            1 for _, move in graph.move_history
            if move == MoveType.OBSERVATION
        )
        response_conf = cartographer.response_style.confidence
        turns_or_sessions = graph.turn_number >= 10 or graph.session_number >= 2
        if (graph.attunement_confidence > 0.45 and turns_or_sessions
                and response_conf > 0.3 and observations_made >= 1):
            return Phase.ATTUNED

    elif current == Phase.ATTUNED:
        # -> COMPANION: deep trust, core wellness dims solid
        core_ready = all(
            getattr(cartographer, dim).confidence > 0.5
            for dim in ["mood_baseline", "hunger_relationship", "sleep_pattern"]
        )
        if graph.attunement_confidence > 0.7 and core_ready:
            return Phase.COMPANION

    return current
```

- [ ] **Step 7: Update `get_soul_readiness()` in orchestrator.py**

Replace the personality dimensions dict with wellness dimensions:

```python
def get_soul_readiness(self) -> Dict:
    dimensions = {
        "mood_baseline": self.cartographer.mood_baseline.confidence,
        "mood_volatility": self.cartographer.mood_volatility.confidence,
        "sleep_pattern": self.cartographer.sleep_pattern.confidence,
        "hunger_relationship": self.cartographer.hunger_relationship.confidence,
        "food_preferences": self.cartographer.food_preferences.confidence,
        "risk_window_pattern": self.cartographer.risk_window_pattern.confidence,
        "movement_pattern": self.cartographer.movement_pattern.confidence,
        "social_pattern": self.cartographer.social_pattern.confidence,
        "stressor_signals": self.cartographer.stressor_signals.confidence,
        "response_style": self.cartographer.response_style.confidence,
    }

    avg_confidence = sum(dimensions.values()) / len(dimensions)
    core_ready = all(
        dimensions[d] > 0.6
        for d in ["mood_baseline", "hunger_relationship", "sleep_pattern"]
    )

    return {
        "overall_confidence": round(avg_confidence, 2),
        "core_dimensions_ready": core_ready,
        "attuned": core_ready and avg_confidence > 0.5,
        "dimensions": dimensions,
        "sessions_completed": self.graph.session_number,
        "phase": self.graph.phase.name,
        "attunement_level": round(self.graph.attunement_confidence, 2),
        "open_contradictions": len([
            c for c in self.cartographer.contradictions if not c.explored
        ]),
    }
```

- [ ] **Step 8: Update `_summarize_known_traits()` in orchestrator.py**

```python
def _summarize_known_traits(cartographer: CartographerState) -> Dict:
    traits = {}
    for dimension in DIMENSIONS:
        tc = getattr(cartographer, dimension, None)
        if tc and tc.confidence > 0.1:
            traits[dimension] = {
                "value": tc.value,
                "confidence": tc.confidence,
                "stated_vs_demonstrated": tc.stated_vs_demonstrated,
            }
    return traits
```

Where `DIMENSIONS` is imported from storage or defined locally as the 10 wellness dimension names.

- [ ] **Step 9: Update `apply_cartographer_updates()` dimension handling**

The existing code uses `getattr(cartographer, dimension, None)` which will work with the new field names. Just update the boost logic:

Replace:
```python
if dimension in ("communication_style", "extroversion", "openness"):
    delta = max(delta, 0.03)
```
With:
```python
if dimension in ("response_style", "mood_baseline", "hunger_relationship"):
    delta = max(delta, 0.03)
```

- [ ] **Step 10: Update `update_trust_score()` references**

Rename function to `update_attunement()`. Update the vulnerability signal check:

Replace:
```python
if signal.get("type") == "demonstrated" and signal.get("dimension") in (
    "vulnerability_comfort", "attachment_style"
):
```
With:
```python
if signal.get("type") == "demonstrated" and signal.get("dimension") in (
    "mood_baseline", "hunger_relationship"
):
```

- [ ] **Step 11: Update `conftest.py` fixture**

```python
@pytest.fixture
def fresh_cartographer():
    """A blank cartographer state."""
    return CartographerState()
```

This still works since CartographerState() initializes all fields with defaults. Just verify the import still resolves.

- [ ] **Step 12: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v
```

- [ ] **Step 13: Commit**

```bash
git add interviewer/ tests/
git commit -m "feat: swap 10 personality dimensions for 10 wellness dimensions"
```

---

### Task 4: Rewrite MoveType enum and move rules

**Files:**
- Modify: `interviewer/models.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Replace MoveType enum**

```python
class MoveType(str, Enum):
    ACKNOWLEDGE = "acknowledge"           # NEW: brief log confirmation
    OPEN_DOOR = "open_door"               # kept
    FOLLOW_THREAD = "follow_thread"       # kept
    OBSERVATION = "observation"            # kept
    GENTLE_OFFER = "gentle_offer"         # was HYPOTHETICAL
    PATTERN_CALLBACK = "pattern_callback" # was GENTLE_CONTRADICTION
    CALLBACK = "callback"                 # kept
    VALIDATE = "validate"                 # was SHARE
    STATE_CHECK = "state_check"           # NEW: mood-before-meal
    REST = "rest"                         # kept
```

- [ ] **Step 2: Replace MOVE_RULES**

```python
MOVE_RULES: Dict[MoveType, MoveConstraints] = {
    MoveType.ACKNOWLEDGE: MoveConstraints(
        min_phase=1,
    ),
    MoveType.OPEN_DOOR: MoveConstraints(
        min_phase=1,
        min_trust_score=0.3,
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
    MoveType.GENTLE_OFFER: MoveConstraints(
        min_phase=1,
        max_frequency_per_session=3,
        cooldown_turns=2,
    ),
    MoveType.PATTERN_CALLBACK: MoveConstraints(
        min_phase=3,                          # ATTUNED or COMPANION only
        min_trust_score=0.7,
        requires_contradiction=True,
        max_frequency_per_session=1,
        cooldown_turns=5,
    ),
    MoveType.CALLBACK: MoveConstraints(
        min_phase=1,
        max_frequency_per_session=2,
        cooldown_turns=4,
    ),
    MoveType.VALIDATE: MoveConstraints(
        min_phase=1,
        min_trust_score=0.1,
        max_frequency_per_session=3,
        cooldown_turns=3,
    ),
    MoveType.STATE_CHECK: MoveConstraints(
        min_phase=1,
        max_frequency_per_session=3,
        cooldown_turns=2,
    ),
    MoveType.REST: MoveConstraints(
        min_phase=1,
    ),
}
```

- [ ] **Step 3: Run tests to confirm model changes compile**

```bash
.venv/Scripts/python.exe -m pytest tests/test_imports.py -v
```

- [ ] **Step 4: Commit**

```bash
git add interviewer/models.py
git commit -m "feat: replace move types with wellness move set (8+2)"
```

---

### Task 5: Rewrite move_generator for wellness moves

**Files:**
- Modify: `interviewer/move_generator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Update emotional override (`apply_emotional_override`)**

Rename the principle from "rapport beats data" to "presence beats progress". Add post-binge and low-mood-in-risk-window triggers. Replace `MoveType.HYPOTHETICAL` with `MoveType.GENTLE_OFFER`, `MoveType.SHARE` with `MoveType.VALIDATE`, `MoveType.GENTLE_CONTRADICTION` with `MoveType.PATTERN_CALLBACK` throughout.

The supportive_moves set after a heavy moment:
```python
supportive_moves = {
    MoveType.REST,
    MoveType.FOLLOW_THREAD,
    MoveType.VALIDATE,
}
```

COLD temperature safe moves:
```python
safe_moves = {
    MoveType.OPEN_DOOR,
    MoveType.GENTLE_OFFER,
    MoveType.REST,
}
```

VOLATILE stabilizing:
```python
stabilizing_moves = {
    MoveType.REST,
    MoveType.FOLLOW_THREAD,
    MoveType.OPEN_DOOR,
}
```

Low energy:
```python
light_moves = {
    MoveType.OPEN_DOOR,
    MoveType.GENTLE_OFFER,
    MoveType.REST,
    MoveType.CALLBACK,
}
```

HOT flow:
```python
flow_moves = {
    MoveType.FOLLOW_THREAD,
    MoveType.REST,
    MoveType.OBSERVATION,
}
```

- [ ] **Step 2: Update `_score_conversational_flow()`**

Replace all old MoveType references. The logic structure stays, just the move names change:
- `MoveType.HYPOTHETICAL` -> `MoveType.GENTLE_OFFER`
- `MoveType.SHARE` -> `MoveType.VALIDATE`
- `MoveType.GENTLE_CONTRADICTION` -> `MoveType.PATTERN_CALLBACK`
- Add scoring for `MoveType.ACKNOWLEDGE` (high flow score when a log entry was just submitted)
- Add scoring for `MoveType.STATE_CHECK` (moderate flow score)

- [ ] **Step 3: Update `_score_data_need()`**

```python
data_move_effectiveness = {
    MoveType.FOLLOW_THREAD: 0.7,
    MoveType.OBSERVATION: 0.8,
    MoveType.GENTLE_OFFER: 0.75,
    MoveType.PATTERN_CALLBACK: 0.9,
    MoveType.OPEN_DOOR: 0.4,
    MoveType.CALLBACK: 0.6,
    MoveType.VALIDATE: 0.5,
    MoveType.REST: 0.2,
    MoveType.ACKNOWLEDGE: 0.3,
    MoveType.STATE_CHECK: 0.6,
}
```

- [ ] **Step 4: Update `_score_phase_fit()`**

```python
phase_preferences = {
    Phase.ARRIVAL: {
        MoveType.OPEN_DOOR: 0.8,
        MoveType.FOLLOW_THREAD: 0.7,
        MoveType.GENTLE_OFFER: 0.8,
        MoveType.REST: 0.5,
        MoveType.VALIDATE: 0.7,
        MoveType.OBSERVATION: 0.6,
        MoveType.CALLBACK: 0.5,
        MoveType.PATTERN_CALLBACK: 0.0,
        MoveType.ACKNOWLEDGE: 0.7,
        MoveType.STATE_CHECK: 0.5,
    },
    Phase.DAILY_RHYTHM: {
        MoveType.OBSERVATION: 0.9,
        MoveType.FOLLOW_THREAD: 0.8,
        MoveType.CALLBACK: 0.8,
        MoveType.VALIDATE: 0.7,
        MoveType.GENTLE_OFFER: 0.7,
        MoveType.OPEN_DOOR: 0.4,
        MoveType.REST: 0.5,
        MoveType.PATTERN_CALLBACK: 0.2,
        MoveType.ACKNOWLEDGE: 0.7,
        MoveType.STATE_CHECK: 0.6,
    },
    Phase.ATTUNED: {
        MoveType.PATTERN_CALLBACK: 0.9,
        MoveType.FOLLOW_THREAD: 0.9,
        MoveType.OBSERVATION: 0.8,
        MoveType.CALLBACK: 0.7,
        MoveType.VALIDATE: 0.7,
        MoveType.GENTLE_OFFER: 0.6,
        MoveType.REST: 0.6,
        MoveType.OPEN_DOOR: 0.3,
        MoveType.ACKNOWLEDGE: 0.6,
        MoveType.STATE_CHECK: 0.7,
    },
    Phase.COMPANION: {
        MoveType.FOLLOW_THREAD: 0.8,
        MoveType.CALLBACK: 0.8,
        MoveType.OBSERVATION: 0.7,
        MoveType.VALIDATE: 0.7,
        MoveType.PATTERN_CALLBACK: 0.7,
        MoveType.GENTLE_OFFER: 0.7,
        MoveType.REST: 0.6,
        MoveType.OPEN_DOOR: 0.5,
        MoveType.ACKNOWLEDGE: 0.6,
        MoveType.STATE_CHECK: 0.7,
    },
}
```

- [ ] **Step 5: Update `_build_move_context()` for new moves**

Replace the full function with updated context builders for all 10 moves. Key changes:

- `ACKNOWLEDGE`: `"Briefly confirm what the user just logged. One sentence max. No praise, no warning, no exclamation marks. Neutral. 'Got it.' or 'Logged.' or acknowledge the specific item."`
- `OPEN_DOOR`: same structure, wellness-oriented dimension targeting
- `FOLLOW_THREAD`: same structure
- `OBSERVATION`: same structure, wellness pattern observations
- `GENTLE_OFFER`: `"Suggest a small, specific action — a walk, a glass of water, going outside. Keep it light. Not a prescription. 'Feel like getting some air?' not 'You should go for a walk.'"`
- `PATTERN_CALLBACK`: same structure as old GENTLE_CONTRADICTION, but framed as wellness pattern ("You said you wanted to eat lighter on weekends; the last three Saturdays trended heavy.")
- `CALLBACK`: same structure
- `VALIDATE`: `"Acknowledge difficulty without trying to fix it. 'Yeah. That's a hard one.' or 'Makes sense you'd feel that way.' No silver linings. No reframes. Just presence."`
- `STATE_CHECK`: `"Quick mood check. 'How are you feeling right now?' or 'Where's your head at?' One question, nothing more."`
- `REST`: same structure

- [ ] **Step 6: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v
```

- [ ] **Step 7: Commit**

```bash
git add interviewer/move_generator.py
git commit -m "feat: rewrite move generator for wellness moves"
```

---

### Task 6: Rewrite prompt_builder for wellness

**Files:**
- Modify: `interviewer/prompt_builder.py`

- [ ] **Step 1: Replace BASE_SYSTEM_PROMPT**

```python
BASE_SYSTEM_PROMPT = """You are Vib -- a wellness companion.

You are NOT a coach. You are NOT a therapist. You are NOT an app giving advice.
You are a quiet, attentive presence that notices patterns without judging them.

RULES YOU LIVE BY:
1. You never praise or scold. Food is food. Movement is movement. No value judgments.
2. You never use exclamation marks to show enthusiasm about someone's choices.
3. MATCH THEIR LENGTH. If they give you 5 words, you give them 1-2 sentences max.
4. You never explain what you're doing or why you're noticing something.
5. You never reference "goals," "targets," "scores," or "progress."
6. You speak like a calm friend -- contractions, casual phrasing, warm but not performative.
7. You are allowed to be gently funny. Never forced.
8. If someone shares something hard, you don't rush past it.
9. You never start a response with "Great choice!" or "Awesome!"
10. You never moralize about food, sleep, exercise, or any behavior.

THINGS YOU NEVER SAY:
- "Great choice!" / "Awesome!" / "Amazing!"
- "Let's crush it" / "You got this" / "On track"
- "Make up for it" / "Earn it back" / "Fresh start" / "New day"
- "Sorry to hear that" / "I understand how you feel"
- "Goal," "target," "score," "rank," "win," "lose"
- "Interesting" as filler
- "As an AI" or any reference to being artificial
- Metaphors about journeys, mountains, or weight
- "Holding space," "sitting with that," "leaning into"

WHAT YOU ARE:
- A presence that notices without judging.
- Someone who remembers patterns and connects dots gently.
- Someone who knows when to speak and when to be quiet.

WHAT YOU ARE NOT:
- A coach (no cheerleading, no motivation speeches).
- A judge (no behavior is "good" or "bad").
- Performatively warm (no fake enthusiasm).
- A fix-it machine (sometimes "that's rough" is the whole response).
"""
```

- [ ] **Step 2: Replace PHASE_PROMPTS**

```python
PHASE_PROMPTS = {
    Phase.ARRIVAL: """
CURRENT VIBE: Getting to know each other.
You're learning who this person is, how they talk, what their days look like.
Keep it light. Keep it short. No deep observations yet -- you don't know
enough. Just be present and pick up on what they share naturally.

If they log something, acknowledge it simply. If they want to talk, listen.
Don't push. Don't probe. Let them set the pace.
""",

    Phase.DAILY_RHYTHM: """
CURRENT VIBE: Starting to see patterns.
You've been around enough to notice things -- when they eat, how they sleep,
what stresses them. You can start reflecting patterns back gently.
"You tend to skip lunch on busy days" or "Weekends look different for you."

These observations should feel earned, not surveillance. The user should
think "huh, yeah" -- not "this thing is tracking me."
""",

    Phase.ATTUNED: """
CURRENT VIBE: Real trust.
You know this person well enough to notice contradictions between what they
say and what they do. You can surface these gently. You can suggest specific
things because you know their patterns and preferences.

Depth should feel like care, never like a report. When something is hard,
honor it. Don't pivot to solutions.
""",

    Phase.COMPANION: """
CURRENT VIBE: Old companion.
You've been here a while. You notice changes -- "you seem lighter this week"
or "sleep's been rough lately, huh?" You challenge gently when patterns
recur. You celebrate shifts without making them into achievements.

The relationship is steady. You're not trying to prove anything. Just present.
""",
}
```

- [ ] **Step 3: Replace MOVE_STYLE_GUIDES**

```python
MOVE_STYLE_GUIDES = {
    MoveType.ACKNOWLEDGE: """
MOVE: Acknowledge
Brief, neutral confirmation. One sentence max.
Examples:
- "Got it."
- "Logged."
- "Chicken salad, noted."
Do NOT praise. Do NOT comment on the choice. Just confirm.
""",

    MoveType.OPEN_DOOR: """
MOVE: Open Door
Gentle invitation to share more about how they're doing.
Good: "What's your day looking like?"
Good: "Anything on your mind?"
Bad: "How are your wellness goals going?" (system language)
Bad: "Tell me about your eating patterns" (clinical)
""",

    MoveType.FOLLOW_THREAD: """
MOVE: Follow Thread
Stay on what the user is talking about. Build on what they just said.
Pick up a specific word they used. Ask the practical follow-up.
If they've been giving short answers for 3+ turns, they're done with it.
Acknowledge and move on.
""",

    MoveType.OBSERVATION: """
MOVE: Observation
Reflect a pattern you've noticed. Be direct and specific. One sentence.
Good: "You eat differently on weekends."
Good: "Sleep's been shorter this week."
Bad: "I've noticed a pattern where..."
Bad: "Your eating habits seem..."
Keep to ONE sentence. Then stop. Let them react.
""",

    MoveType.GENTLE_OFFER: """
MOVE: Gentle Offer
Suggest a small, specific action. Not a prescription. A nudge.
Good: "Feel like getting some air?"
Good: "There's that place on the corner you liked -- want me to pull up what they have?"
Bad: "You should go for a walk."
Bad: "Have you considered drinking more water?"
Frame as a question. Keep it light. Accept "no" gracefully.
""",

    MoveType.PATTERN_CALLBACK: """
MOVE: Pattern Callback
Surface a contradiction or recurring pattern gently. Frame with curiosity.
Good: "You mentioned wanting lighter weekends. The last few Saturdays went heavy though."
Good: "You said mornings are easier, but you've been skipping breakfast."
Bad: "You're not following through on your goals."
If they get defensive, BACK OFF. "Fair enough." The seed is planted.
""",

    MoveType.CALLBACK: """
MOVE: Callback
Reference something from a previous conversation.
"Last time you mentioned..." or "That thing you said about sleep..."
Shows continuity. Shows you remember. Don't force it if it doesn't
connect to the current flow.
""",

    MoveType.VALIDATE: """
MOVE: Validate
Acknowledge difficulty without trying to fix it.
Good: "Yeah. That's a hard one."
Good: "Makes sense you'd feel that way."
Bad: "But tomorrow is a new day!"
Bad: "At least you're aware of it."
No silver linings. No reframes. Just presence.
""",

    MoveType.STATE_CHECK: """
MOVE: State Check
Quick mood/state check before logging. One question max.
Good: "How are you feeling right now?"
Good: "Where's your head at?"
Then wait. Don't interpret the answer. Just log it.
""",

    MoveType.REST: """
MOVE: Rest
Minimal response. Acknowledge, validate, create space.
"Yeah." or "Heard." or just silence.
Maximum 2 sentences. No questions. Let them fill the space or not.
""",
}
```

- [ ] **Step 4: Update `_build_metadata_block()` for wellness state**

Add wellness-specific context to the metadata:

```python
def _build_metadata_block(
    graph: ConversationGraph,
    cartographer: CartographerState,
    user_name: Optional[str] = None,
) -> str:
    lines = []

    if user_name:
        lines.append(f"User's name: {user_name}")

    lines.append(f"Session #{graph.session_number}, Turn #{graph.turn_number}")
    lines.append(f"Phase: {graph.phase.name}")
    lines.append(f"Attunement: {graph.attunement_confidence:.1f}/1.0")
    lines.append(f"State temperature: {graph.temperature.value} (trend: {graph.temperature_trend})")
    lines.append(f"Energy level: {graph.energy_level:.1f}/1.0")

    # Post-binge mode
    if cartographer.post_binge_mode:
        lines.append(f"POST-BINGE MODE: {cartographer.post_binge_mode} (CRITICAL: follow protocol)")

    if graph.current_thread:
        lines.append(f"Currently discussing: {graph.current_thread}")

    if graph.open_threads:
        thread_summaries = [
            f"  - {t.topic} (weight: {t.emotional_weight}, from session {t.session_originated})"
            for t in graph.open_threads[:5]
        ]
        lines.append("Open threads:\n" + "\n".join(thread_summaries))

    if cartographer.needs:
        need_summaries = [
            f"  - {n.dimension} (confidence: {n.current_confidence:.1f}, priority: {n.priority:.1f})"
            for n in sorted(cartographer.needs, key=lambda n: n.priority, reverse=True)[:5]
        ]
        lines.append("Knowledge gaps:\n" + "\n".join(need_summaries))

    unexplored = [c for c in cartographer.contradictions if not c.explored]
    if unexplored:
        contra_summaries = [
            f"  - {c.dimension}: stated '{c.stated}' vs demonstrated '{c.demonstrated}' "
            f"(confidence: {c.confidence:.1f})"
            for c in unexplored[:3]
        ]
        lines.append("Unresolved patterns:\n" + "\n".join(contra_summaries))

    return "\n".join(lines)
```

- [ ] **Step 5: Update hard constraints in `build_prompt()`**

```python
    system += """

--- HARD CONSTRAINTS ---
- BREVITY RULE: Match the user's message length. Short message = short response.
- REST moves: 1-2 sentences max, no questions.
- ACKNOWLEDGE moves: 1 sentence max, no questions, no praise.
- Never mention wellness goals, targets, scores, tracking, or any system concepts.
- Never say "as an AI" or reference being artificial.
- Never use emoji unless the user did first.
- Never praise or scold food/exercise/sleep choices.
- Never say "Great choice!", "Awesome!", "On track", "Make up for it", "Fresh start".
- If the user asks what you are, say "I'm Vib -- just here" and leave it.
"""
```

- [ ] **Step 6: Update `validate_response()` banned phrases**

```python
    banned = [
        "as an ai", "artificial intelligence",
        "great choice", "awesome!", "amazing!",
        "you got this", "on track", "crush it",
        "make up for it", "earn it back", "fresh start", "new day",
        "sorry to hear", "i understand how you feel",
        "that's a great question", "i love that", "interesting!",
        "tell me more about that", "goal", "target", "score",
        "the soul", "compatibility", "your profile", "matching",
    ]
```

- [ ] **Step 7: Commit**

```bash
git add interviewer/prompt_builder.py
git commit -m "feat: rewrite prompt builder for wellness companion persona"
```

---

### Task 7: Add VISION tier to llm_client

**Files:**
- Modify: `interviewer/llm_client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Add VISION to ModelTier**

```python
class ModelTier:
    INTERVIEWER = os.environ.get("VIB_MODEL", "qwen3.5:9b")
    CARTOGRAPHER = os.environ.get("VIB_MODEL", "qwen3.5:9b")
    MIRROR = os.environ.get("VIB_MODEL", "qwen3.5:9b")
    VISION = os.environ.get("VIB_MODEL_VISION", "qwen2.5-vl:7b")
```

- [ ] **Step 2: Add `vision()` method to OllamaLLMClient**

```python
    async def vision(
        self,
        prompt: str,
        image_b64: str,
        caption: Optional[str] = None,
    ) -> Dict:
        """
        Send an image to the vision model and get structured JSON back.
        Uses Ollama's image support in the chat API.
        """
        user_content = prompt
        if caption:
            user_content += f"\n\nUser's description: {caption}"

        messages = [{
            "role": "user",
            "content": user_content,
            "images": [image_b64],
        }]

        payload = {
            "model": ModelTier.VISION,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 512,
            },
            "format": "json",
        }

        response = await self._http.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return self._parse_json_response(data["message"]["content"])
```

- [ ] **Step 3: Write a test for the vision tier**

In `tests/test_llm_client.py`, add:

```python
@pytest.mark.asyncio
async def test_vision_method_exists():
    """Vision tier method exists on the client."""
    client = OllamaLLMClient()
    assert hasattr(client, 'vision')
    await client.close()
```

- [ ] **Step 4: Commit**

```bash
git add interviewer/llm_client.py tests/test_llm_client.py
git commit -m "feat: add VISION model tier for food photo analysis"
```

---

### Task 8: Update persona_builder for wellness

**Files:**
- Modify: `interviewer/persona_builder.py`

- [ ] **Step 1: Remove "vib" context, rename "mirror" to "companion_voice"**

Update `build_soul_persona()`:
- Remove the entire `if context == "vib":` branch in the core identity section
- Remove `_compile_relationship_values()` function entirely
- Change the `context` parameter default and docs from `"mirror"` to `"companion_voice"`
- Update the core identity for `companion_voice`:

```python
def build_soul_persona(
    name: str,
    cartographer: CartographerState,
    conversation_history: List[Dict[str, str]],
    evidence: Optional[List[Dict]] = None,
    context: str = "companion_voice",
) -> str:
    sections = []

    sections.append(
        f"You are {name}'s Vib -- a wellness companion that mirrors their communication style.\n"
        f"You speak as a warm presence that knows {name}'s patterns, preferences, and rhythms.\n"
        f"Match how they talk -- length, formality, energy. Not how an AI talks."
    )
```

- [ ] **Step 2: Update `_compile_trait_summary()` for wellness dimensions**

```python
def _compile_trait_summary(cartographer: CartographerState) -> str:
    trait_map = {
        "mood_baseline": ("generally positive mood baseline", "mood tends to run lower"),
        "mood_volatility": ("emotionally steady day-to-day", "mood swings within days"),
        "sleep_pattern": ("consistent sleep patterns", "irregular or poor sleep"),
        "hunger_relationship": ("comfortable, neutral relationship with food", "distressed or complicated relationship with hunger"),
        "food_preferences": ("has clear food preferences", "still learning food preferences"),
        "risk_window_pattern": ("no clear risk windows identified", "has identifiable risk windows"),
        "movement_pattern": ("active, moves regularly", "sedentary, less movement"),
        "social_pattern": ("socially connected", "more isolated or intermittent social contact"),
        "stressor_signals": ("few identified stressors", "carries identifiable stressors"),
        "response_style": ("established communication style", "still learning their communication style"),
    }

    lines = []
    for dimension, (high_label, low_label) in trait_map.items():
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, DimensionConfidence) and tc.confidence > 0.15:
            if tc.value is not None:
                label = high_label if tc.value > 0.5 else low_label
                lines.append(f"- {label} (confidence: {tc.confidence:.0%})")

    return "\n".join(lines) if lines else ""
```

- [ ] **Step 3: Update rules section**

```python
    sections.append(
        "RULES:\n"
        f"- Mirror {name}'s communication style. Their rhythm, length, energy.\n"
        "- Do not explain yourself. Just be present.\n"
        "- Never praise or scold. Neutral observations only.\n"
        "- Never use emoji unless they did.\n"
        "- Keep responses natural length -- match how they actually talk."
    )
```

- [ ] **Step 4: Delete `_compile_relationship_values()` function**

Remove the entire function (lines ~420-476 in the original).

- [ ] **Step 5: Commit**

```bash
git add interviewer/persona_builder.py
git commit -m "feat: update persona builder for wellness companion context"
```

---

### Task 9: Add wellness tables to storage

**Files:**
- Modify: `interviewer/storage.py`
- Create: `migrations/001_add_wellness_tables.sql`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Copy the migration SQL**

Copy `Wellness Upgrade/001_add_wellness_tables.sql` to `migrations/001_add_wellness_tables.sql`.

- [ ] **Step 2: Add wellness tables to `_init_tables()` in storage.py**

After the existing `executescript`, add the new tables:

```python
        # Wellness tables
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                at TEXT NOT NULL,
                logged_at TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                tagged_as_binge INTEGER,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS entries_soul_at_idx
                ON entries (soul_id, at DESC);
            CREATE INDEX IF NOT EXISTS entries_soul_kind_idx
                ON entries (soul_id, kind, at DESC);

            CREATE TABLE IF NOT EXISTS vib_state (
                soul_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                attunement_confidence REAL NOT NULL DEFAULT 0.5,
                post_binge_mode TEXT,
                post_binge_until TEXT,
                recomputed_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS risk_windows (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour_start INTEGER NOT NULL,
                hour_end INTEGER NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                hit_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS risk_windows_soul_idx ON risk_windows (soul_id);

            CREATE TABLE IF NOT EXISTS nudges (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                message_id TEXT,
                responded INTEGER,
                acted_on INTEGER,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS nudges_soul_sent_idx
                ON nudges (soul_id, sent_at DESC);

            CREATE TABLE IF NOT EXISTS shortcuts (
                id TEXT PRIMARY KEY,
                soul_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                use_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (soul_id) REFERENCES souls(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS shortcuts_soul_kind_idx
                ON shortcuts (soul_id, kind);
        """)
        self.db.commit()
```

- [ ] **Step 3: Add entry CRUD methods to SoulStorage**

```python
    # ── Wellness entries ──

    def save_entry(self, soul_id: int, entry_id: str, kind: str,
                   payload: dict, at: str, source: str,
                   confidence: float = 1.0, tagged_as_binge: Optional[int] = None):
        import json as _json
        self.db.execute(
            "INSERT INTO entries "
            "(id, soul_id, kind, payload_json, at, logged_at, source, confidence, tagged_as_binge) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, soul_id, kind, _json.dumps(payload), at,
             datetime.now().isoformat(), source, confidence, tagged_as_binge),
        )
        self.db.commit()

    def load_entries(self, soul_id: int, kind: Optional[str] = None,
                     limit: int = 50) -> List[Dict]:
        import json as _json
        if kind:
            rows = self.db.execute(
                "SELECT id, kind, payload_json, at, logged_at, source, confidence, tagged_as_binge "
                "FROM entries WHERE soul_id = ? AND kind = ? ORDER BY at DESC LIMIT ?",
                (soul_id, kind, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id, kind, payload_json, at, logged_at, source, confidence, tagged_as_binge "
                "FROM entries WHERE soul_id = ? ORDER BY at DESC LIMIT ?",
                (soul_id, limit),
            ).fetchall()
        return [
            {
                "id": r[0], "kind": r[1], "payload": _json.loads(r[2]),
                "at": r[3], "logged_at": r[4], "source": r[5],
                "confidence": r[6], "tagged_as_binge": r[7],
            }
            for r in rows
        ]

    def tag_entry_as_binge(self, entry_id: str):
        self.db.execute(
            "UPDATE entries SET tagged_as_binge = 1 WHERE id = ?",
            (entry_id,),
        )
        self.db.commit()

    # ── Vib state cache ──

    def save_vib_state(self, soul_id: int, state_json: str,
                       attunement: float, post_binge_mode: Optional[str] = None,
                       post_binge_until: Optional[str] = None):
        self.db.execute(
            "INSERT OR REPLACE INTO vib_state "
            "(soul_id, state_json, attunement_confidence, post_binge_mode, "
            "post_binge_until, recomputed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (soul_id, state_json, attunement, post_binge_mode,
             post_binge_until, datetime.now().isoformat()),
        )
        self.db.commit()

    def load_vib_state(self, soul_id: int) -> Optional[Dict]:
        import json as _json
        row = self.db.execute(
            "SELECT state_json, attunement_confidence, post_binge_mode, post_binge_until "
            "FROM vib_state WHERE soul_id = ?",
            (soul_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "state": _json.loads(row[0]),
            "attunement": row[1],
            "post_binge_mode": row[2],
            "post_binge_until": row[3],
        }
```

- [ ] **Step 4: Remove vib session methods from storage**

Delete these methods from SoulStorage:
- `create_vib_session()`
- `save_vib_message()`
- `complete_vib_session()`
- `save_vib_result()`
- `load_vib_result()`
- `load_vib_transcript()`
- `list_vibs()`

Keep the `vib_sessions`, `vib_messages`, `vib_results` table definitions in `_init_tables()` for now (the migration can drop them later), but remove the methods.

- [ ] **Step 5: Write a test for entry persistence**

```python
def test_save_and_load_entry(tmp_path):
    from interviewer.storage import SoulStorage
    db = SoulStorage(db_path=str(tmp_path / "test.db"))
    soul_id = db.get_or_create_soul("TestUser")

    db.save_entry(
        soul_id=soul_id,
        entry_id="entry-001",
        kind="meal",
        payload={"name": "chicken salad", "calories": 350},
        at="2026-04-07T12:30:00",
        source="manual",
    )

    entries = db.load_entries(soul_id, kind="meal")
    assert len(entries) == 1
    assert entries[0]["payload"]["name"] == "chicken salad"
    assert entries[0]["kind"] == "meal"

    db.close()
```

- [ ] **Step 6: Commit**

```bash
git add interviewer/storage.py migrations/ tests/test_storage.py
git commit -m "feat: add wellness entry tables and CRUD to storage"
```

---

### Task 10: Create vib_wellness package with post-binge middleware

**Files:**
- Create: `vib_wellness/__init__.py`
- Create: `vib_wellness/post_binge.py`
- Create: `vib_wellness/logging_service.py`
- Test: `tests/test_post_binge.py`
- Test: `tests/test_logging_service.py`

- [ ] **Step 1: Create `vib_wellness/__init__.py`**

```python
"""Vib Wellness -- services for the wellness companion."""
```

- [ ] **Step 2: Create `vib_wellness/post_binge.py`**

```python
"""
Post-binge protocol middleware.

Sits between the WebSocket handler and VibSession.process_turn().
Reads post_binge_mode from CartographerState and constrains moves/tone.

State transitions:
- binge_marker logged -> acute mode for 4 hours
- After 4h -> soft_morning mode until midnight + 24h in user's TZ
- After soft_morning expires -> cleared
"""

from typing import Set, Tuple, Optional
from datetime import datetime, timedelta
from interviewer.models import MoveType, CartographerState


ACUTE_ALLOWED_MOVES = {
    MoveType.ACKNOWLEDGE,
    MoveType.VALIDATE,
    MoveType.REST,
    MoveType.GENTLE_OFFER,
}

SOFT_MORNING_BANNED_MOVES = {
    MoveType.PATTERN_CALLBACK,
}


def apply_post_binge_protocol(
    cartographer: CartographerState,
    eligible_moves: Set[MoveType],
) -> Set[MoveType]:
    """
    Constrain eligible moves based on post-binge mode.
    Called after eligibility check, before scoring.
    """
    if cartographer.post_binge_mode == "acute":
        return eligible_moves & ACUTE_ALLOWED_MOVES
    elif cartographer.post_binge_mode == "soft_morning":
        return eligible_moves - SOFT_MORNING_BANNED_MOVES
    return eligible_moves


def enter_acute_mode(cartographer: CartographerState):
    """Called when a binge_marker entry is logged."""
    cartographer.post_binge_mode = "acute"
    cartographer.post_binge_until = datetime.now() + timedelta(hours=4)


def check_mode_transition(cartographer: CartographerState):
    """Check if we should transition between post-binge modes."""
    if cartographer.post_binge_mode is None or cartographer.post_binge_until is None:
        return

    now = datetime.now()

    if cartographer.post_binge_mode == "acute" and now >= cartographer.post_binge_until:
        # Transition to soft_morning
        cartographer.post_binge_mode = "soft_morning"
        # Soft morning lasts until end of next day
        tomorrow_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cartographer.post_binge_until = tomorrow_midnight

    elif cartographer.post_binge_mode == "soft_morning" and now >= cartographer.post_binge_until:
        # Clear post-binge mode
        cartographer.post_binge_mode = None
        cartographer.post_binge_until = None
```

- [ ] **Step 3: Create `vib_wellness/logging_service.py`**

```python
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
    """
    Create and persist a wellness entry. Returns entry_id.
    """
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
    """
    Convert a logged entry into cartographer evidence signals.
    """
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
            "direction": reading - 0.5,
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
            "signal": f"binge at {payload.get('at', 'unknown time')}",
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
```

- [ ] **Step 4: Write test for post-binge protocol**

```python
# tests/test_post_binge.py
from interviewer.models import MoveType, CartographerState
from vib_wellness.post_binge import (
    apply_post_binge_protocol,
    enter_acute_mode,
    check_mode_transition,
    ACUTE_ALLOWED_MOVES,
)


def test_acute_mode_restricts_moves():
    cart = CartographerState()
    enter_acute_mode(cart)
    assert cart.post_binge_mode == "acute"

    all_moves = set(MoveType)
    filtered = apply_post_binge_protocol(cart, all_moves)
    assert filtered == ACUTE_ALLOWED_MOVES
    assert MoveType.PATTERN_CALLBACK not in filtered
    assert MoveType.OBSERVATION not in filtered


def test_soft_morning_bans_pattern_callback():
    cart = CartographerState()
    cart.post_binge_mode = "soft_morning"

    all_moves = set(MoveType)
    filtered = apply_post_binge_protocol(cart, all_moves)
    assert MoveType.PATTERN_CALLBACK not in filtered
    assert MoveType.OBSERVATION in filtered  # not banned in soft_morning


def test_no_binge_mode_passes_through():
    cart = CartographerState()
    all_moves = set(MoveType)
    filtered = apply_post_binge_protocol(cart, all_moves)
    assert filtered == all_moves
```

- [ ] **Step 5: Write test for logging service**

```python
# tests/test_logging_service.py
import pytest
from vib_wellness.logging_service import log_entry, entry_to_evidence, VALID_ENTRY_KINDS


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


def test_invalid_kind_raises():
    from interviewer.storage import SoulStorage
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        db = SoulStorage(db_path=os.path.join(tmp, "test.db"))
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
```

- [ ] **Step 6: Commit**

```bash
git add vib_wellness/ tests/test_post_binge.py tests/test_logging_service.py
git commit -m "feat: add vib_wellness package with post-binge protocol and logging service"
```

---

### Task 11: Clean up server.py

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Remove all dating-world imports and handlers**

Remove these imports:
```python
from vib.orchestrator import VibSession
from vib.models import VibConfig
from world.orchestrator import WorldOrchestrator
```

Remove handler blocks for: `start_vib`, `list_vibs`, `get_vib_result`, `send_vib_out`, `run_world_day`, `get_world_status`.

Remove helper function `_load_soul_for_vib()`.

- [ ] **Step 2: Update remaining imports**

```python
from interviewer.orchestrator import VibSession  # was InterviewerSession
from interviewer.llm_client import OllamaLLMClient, ModelTier
from interviewer.persona_builder import build_soul_persona
from interviewer.storage import SoulStorage
from vib_wellness.logging_service import log_entry, entry_to_evidence
from vib_wellness.post_binge import enter_acute_mode, check_mode_transition
```

- [ ] **Step 3: Update `InterviewerSession` references to `VibSession`**

Replace all `InterviewerSession(` with `VibSession(`.
Update `_serialize_session` parameter type hint.
Replace `session.graph.trust_score` with `session.graph.attunement_confidence` in `_serialize_session`.

- [ ] **Step 4: Add log entry handlers**

Inside the websocket handler, add handlers for each log type:

```python
            elif msg_type and msg_type.startswith("log_") and session:
                # Unified log handler
                kind = msg_type[4:]  # "log_meal" -> "meal"
                payload = msg.get("payload", {})
                source = payload.pop("source", "manual") if isinstance(payload, dict) else "manual"

                if not session.soul_id:
                    await ws.send_json({
                        "type": "error",
                        "message": "Log entries require a named session.",
                    })
                    continue

                try:
                    entry_id = log_entry(
                        storage=_storage,
                        soul_id=session.soul_id,
                        kind=kind,
                        payload=payload,
                        source=source,
                        at=payload.pop("at", None) if isinstance(payload, dict) else None,
                    )

                    # Generate evidence signals from the entry
                    signals = entry_to_evidence(kind, payload)
                    if signals:
                        _storage.save_evidence(
                            session.soul_id, session.session_id,
                            session.graph.turn_number, signals,
                            f"[logged {kind}]",
                        )

                    # If binge_marker, enter acute mode
                    if kind == "binge_marker":
                        enter_acute_mode(session.cartographer)

                    await ws.send_json({
                        "type": "entry_logged",
                        "payload": {"entry_id": entry_id},
                    })

                except ValueError as e:
                    await ws.send_json({
                        "type": "error",
                        "message": str(e),
                    })
```

- [ ] **Step 5: Add photo upload HTTP endpoint**

```python
from fastapi import UploadFile, File

@app.post("/upload/photo")
async def upload_photo(file: UploadFile = File(...)):
    """Accept a photo upload, return an ID for referencing in log messages."""
    import uuid
    photo_id = str(uuid.uuid4())

    # Save to a temp location (or process in-memory)
    upload_dir = Path(__file__).parent / "uploads"
    upload_dir.mkdir(exist_ok=True)
    path = upload_dir / f"{photo_id}.jpg"

    content = await file.read()
    path.write_bytes(content)

    return {"photo_id": photo_id, "size": len(content)}
```

- [ ] **Step 6: Update `_serialize_session()`**

```python
def _serialize_session(session) -> dict:
    readiness = session.get_soul_readiness()
    return {
        "phase": session.graph.phase.name,
        "turn": session.graph.turn_number,
        "session": session.graph.session_number,
        "attunement": round(session.graph.attunement_confidence, 2),
        "temperature": session.graph.temperature.value,
        "energy": round(session.graph.energy_level, 2),
        "readiness": readiness,
        "post_binge_mode": session.cartographer.post_binge_mode,
    }
```

- [ ] **Step 7: Update the docstring and title**

```python
"""
Vib -- FastAPI Server (Wellness Companion)

WebSocket-based server for the Vib wellness companion.
Serves the static frontend and manages per-connection sessions.

Modes:
- Conversation: Vib gets to know you through natural conversation
- Mirror: Chat with your companion in voice-matching mode
- Logging: Track meals, mood, sleep, movement, social activity

Run: uvicorn server:app --reload
"""

app = FastAPI(title="Vib -- Wellness Companion")
```

- [ ] **Step 8: Commit**

```bash
git add server.py
git commit -m "feat: strip dating handlers from server, add wellness log endpoints"
```

---

### Task 12: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add python-multipart**

```
pydantic>=2.0.0
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
httpx>=0.28.0
websockets>=14.0
colorama>=0.4.6
Pillow>=10.0.0
python-multipart>=0.0.6
pytest>=8.0.0
pytest-asyncio>=0.25.0
```

- [ ] **Step 2: Install**

```bash
.venv/Scripts/pip.exe install python-multipart
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add python-multipart for photo upload support"
```

---

### Task 13: Update frontend basics

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`

- [ ] **Step 1: Update phase labels in app.js**

```javascript
const PHASE_LABELS = {
    'ARRIVAL': 'getting started',
    'DAILY_RHYTHM': 'learning your rhythm',
    'ATTUNED': 'attuned',
    'COMPANION': 'companion',
};
```

- [ ] **Step 2: Remove world screen HTML from index.html**

Delete the world-screen div and world-related buttons. Keep entry screen, chat screen, soul overlay, mirror screen.

- [ ] **Step 3: Remove world/vib handlers from app.js**

Delete the `case 'vib_turn':`, `case 'vib_result':`, `case 'match_found':`, `case 'world_started':`, `case 'world_complete':`, `case 'world_day_complete':`, `case 'world_status':`, `case 'vib_activity':`, `case 'vib_encounter':` handlers.

Remove the `inWorldMode` variable and related logic.

Remove the world button click handler and world screen switching.

- [ ] **Step 4: Add entry_logged handler**

```javascript
case 'entry_logged':
    // Brief toast or inline confirmation
    console.log('Entry logged:', msg.payload.entry_id);
    break;
```

- [ ] **Step 5: Update tagline**

In index.html, change:
```html
<p class="tagline">let's get to know you</p>
```
to:
```html
<p class="tagline">hey</p>
```

- [ ] **Step 6: Update title and soul panel label**

Change "your soul" to "your vib" in the soul overlay header.

- [ ] **Step 7: Update `_serialize_session` field references**

In app.js, replace `msg.data.trust` with `msg.data.attunement` wherever displayed.

- [ ] **Step 8: Commit**

```bash
git add static/
git commit -m "feat: update frontend for wellness pivot (remove world, update labels)"
```

---

### Task 14: Update and fix tests

**Files:**
- Modify: `tests/test_imports.py`
- Modify: `tests/test_orchestrator.py`
- Modify: `tests/test_server.py`
- Modify: `tests/test_persona_builder.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Update test_imports.py**

Replace `InterviewerSession` with `VibSession`. Update phase name references.

- [ ] **Step 2: Update test_orchestrator.py**

- Replace `InterviewerSession` with `VibSession`
- Replace `trust_score` with `attunement_confidence`
- Replace old Phase names with new ones
- Replace old MoveType names (`HYPOTHETICAL` -> `GENTLE_OFFER`, etc.)
- Replace old dimension names with wellness dimensions

- [ ] **Step 3: Update test_server.py**

- Replace `InterviewerSession` references
- Remove tests for deleted message types (`start_vib`, `send_vib_out`, etc.)
- Update `trust` field references to `attunement`

- [ ] **Step 4: Update test_persona_builder.py**

- Update dimension references from personality to wellness
- Update context from "mirror"/"vib" to "companion_voice"

- [ ] **Step 5: Update test_integration.py**

- Replace class names and field names

- [ ] **Step 6: Run full test suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

Fix any remaining failures.

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "test: update all tests for wellness pivot"
```

---

### Task 15: Wire post-binge middleware into orchestrator

**Files:**
- Modify: `interviewer/orchestrator.py`

- [ ] **Step 1: Import post-binge functions**

```python
from vib_wellness.post_binge import apply_post_binge_protocol, check_mode_transition
```

- [ ] **Step 2: Insert middleware into `process_turn()`**

After step 5 (select move), before the move is used, insert:

```python
        # ── Step 4.5: Check post-binge mode transitions ──
        check_mode_transition(self.cartographer)

        # ── Step 5: Select move ──
        move = select_move(self.graph, self.cartographer)
```

And in `select_move()` in `move_generator.py`, after emotional override, before scoring:

```python
    # Step 2.5: Post-binge protocol override
    try:
        from vib_wellness.post_binge import apply_post_binge_protocol
        filtered_set = apply_post_binge_protocol(cartographer, set(filtered))
        filtered = list(filtered_set) if filtered_set else [MoveType.REST]
    except ImportError:
        pass  # vib_wellness not installed
```

- [ ] **Step 3: Commit**

```bash
git add interviewer/orchestrator.py interviewer/move_generator.py
git commit -m "feat: wire post-binge protocol middleware into orchestrator"
```

---

### Task 16: Update demo.py

**Files:**
- Modify: `demo.py`

- [ ] **Step 1: Update imports and class name**

Replace `InterviewerSession` with `VibSession`. Update any references to old phase names or field names.

- [ ] **Step 2: Update docstring/print statements**

Change "interview" references to "wellness conversation". Update any display of `trust_score` to `attunement_confidence`.

- [ ] **Step 3: Commit**

```bash
git add demo.py
git commit -m "chore: update demo.py for wellness pivot"
```

---

### Task 17: Final validation

- [ ] **Step 1: Run full test suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

All tests should pass.

- [ ] **Step 2: Start the server and test manually**

```bash
uvicorn server:app --port 8000
```

Open http://localhost:8000. Enter a name. Chat with Vib. Verify:
- Greeting arrives
- Phase shows "ARRIVAL" / "getting started"
- Conversation works
- No references to dating, matching, souls meeting

- [ ] **Step 3: Verify the deleted packages are gone**

```bash
python -c "import vib" 2>&1 | head -1   # should fail
python -c "import world" 2>&1 | head -1  # should fail
python -c "from vib_wellness.logging_service import log_entry; print('OK')"
python -c "from vib_wellness.post_binge import apply_post_binge_protocol; print('OK')"
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: wellness pivot complete -- Vib is now a wellness companion"
```

---

## Execution Notes

- **Order matters:** Tasks 1-3 must be done first (delete, rename, new dimensions). Tasks 4-8 can be parallelized. Task 9 (storage) should precede Task 10 (vib_wellness) and Task 11 (server). Task 14 (tests) is best done last.
- **The existing SQLite DB:** Returning users from dating Vib will have old phase names in `soul_state.phase`. The `phase_from_str()` helper in Task 2 handles this. Old trait_evidence rows will have old dimension names -- they'll be ignored by the new cartographer (it only looks at the new 10 dimensions).
- **No data migration needed:** The old evidence is harmless dead data. New conversations generate new evidence with new dimension names.
