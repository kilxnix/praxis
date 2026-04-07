"""
The Soul — Interviewer Orchestrator

This is the main loop. It receives user input, runs it through all three
systems, and produces the response. It also handles state transitions
between phases and sessions.

Flow per turn:
1. User says something
2. Cartographer silently analyzes it (updates soul model)
3. Conversation Graph updates (temperature, threads, energy)
4. Move Generator selects the best move
5. Prompt Builder constructs the LLM prompt
6. LLM generates the response
7. Response gets validated
8. State persists for next turn
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from interviewer.models import (
    ConversationGraph, CartographerState, Phase, EmotionalTemperature,
    OpenThread, DimensionConfidence, TraitConfidence, Contradiction,
    CartographerNeeds, MoveType, SelectedMove, phase_from_str
)
from interviewer.move_generator import select_move
from interviewer.prompt_builder import build_prompt, validate_response

try:
    from interviewer.llm_client import SoulLLMClient, ModelTier
except ImportError:
    SoulLLMClient = None
    ModelTier = None


# ─────────────────────────────────────────────
# THE CARTOGRAPHER (System 2)
# ─────────────────────────────────────────────
# This will eventually be its own module. For now, it lives here
# as the analysis pipeline that runs on every user message.

CARTOGRAPHER_SYSTEM_PROMPT = """You are the Soul Cartographer. You analyze user messages and map wellness state.

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


async def analyze_message(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    cartographer: CartographerState,
    graph: ConversationGraph,
    llm_client = None,
) -> Dict:
    """
    Run the Cartographer analysis on a user message.
    Returns structured updates to apply to the state.
    
    In production, this calls the LLM with CARTOGRAPHER_SYSTEM_PROMPT.
    The response is parsed and applied to cartographer + graph state.
    """
    
    # Build the analysis context
    analysis_context = {
        "user_message": user_message,
        "turn_number": graph.turn_number,
        "session_number": graph.session_number,
        "current_temperature": graph.temperature.value,
        "current_thread": graph.current_thread,
        "open_threads": [t.topic for t in graph.open_threads],
        "known_traits": _summarize_known_traits(cartographer),
        "existing_contradictions": [
            {"dimension": c.dimension, "stated": c.stated, "demonstrated": c.demonstrated}
            for c in cartographer.contradictions
        ],
        "recent_conversation": [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation_history[-6:]  # Last 6 messages for context
        ],
    }

    if llm_client:
        return await llm_client.cartographer_analyze(
            system=CARTOGRAPHER_SYSTEM_PROMPT,
            analysis_input=analysis_context,
        )

    # Fallback if no client (development mode)
    return {
        "trait_signals": [],
        "emotional_read": {
            "temperature": graph.temperature.value,
            "trend": "stable",
            "energy": graph.energy_level,
        },
        "thread_updates": [],
        "contradiction_check": None,
        "unclassified": [],
    }


def _summarize_known_traits(cartographer: CartographerState) -> Dict:
    """Summarize what we know for the analysis prompt context."""
    from interviewer.storage import DIMENSIONS
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


# ─────────────────────────────────────────────
# STATE UPDATE ENGINE
# ─────────────────────────────────────────────

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
    # Old personality dims -> closest wellness equivalent
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


def _normalize_dimension(name: str) -> str:
    """Map LLM dimension names to our canonical attribute names."""
    clean = name.lower().strip()
    return _DIMENSION_ALIASES.get(clean, clean)


def _ensure_list(val) -> list:
    """Wrap a single dict in a list if needed."""
    if isinstance(val, dict):
        return [val]
    if isinstance(val, list):
        return val
    return []


def apply_cartographer_updates(
    analysis: Dict,
    cartographer: CartographerState,
    graph: ConversationGraph,
) -> Tuple[CartographerState, ConversationGraph]:
    """
    Apply the Cartographer's analysis to update both state objects.
    """

    # ── Update emotional state on graph ──
    emotional_read = analysis.get("emotional_read", {})
    if emotional_read:
        temp_str = emotional_read.get("temperature", graph.temperature.value)
        try:
            graph.temperature = EmotionalTemperature(temp_str)
        except ValueError:
            pass
        graph.temperature_trend = emotional_read.get("trend", "stable")
        graph.energy_level = emotional_read.get("energy", graph.energy_level)

        # Track heavy moments
        if graph.temperature == EmotionalTemperature.HOT:
            graph.last_heavy_moment_turn = graph.turn_number

    # ── Update trait confidence ──
    for signal in _ensure_list(analysis.get("trait_signals", [])):
        dimension = _normalize_dimension(signal.get("dimension", ""))
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, TraitConfidence):
            # Apply confidence delta — demonstrated signals are worth more
            delta = signal.get("confidence_delta", 0.0)
            if signal.get("type") == "demonstrated":
                delta *= 2.0
            # Boost: short messages still carry signal — brevity itself is data
            if dimension in ("response_style", "mood_baseline", "hunger_relationship"):
                delta = max(delta, 0.03)
            tc.confidence = min(tc.confidence + delta, 1.0)
            tc.evidence_count += 1
            tc.last_updated_session = graph.session_number

            # Track stated vs demonstrated
            signal_type = signal.get("type", "stated")
            if tc.stated_vs_demonstrated is None:
                tc.stated_vs_demonstrated = signal_type
            elif tc.stated_vs_demonstrated != signal_type and tc.stated_vs_demonstrated != "both":
                if tc.stated_vs_demonstrated == "conflicting":
                    pass
                else:
                    tc.stated_vs_demonstrated = "both"

    # ── Update threads ──
    for thread_update in _ensure_list(analysis.get("thread_updates", [])):
        action = thread_update.get("action")
        topic = thread_update.get("topic", "")

        if action == "open":
            graph.open_threads.append(OpenThread(
                topic=topic,
                context=thread_update.get("context", ""),
                emotional_weight=thread_update.get("emotional_weight", 0.5),
                session_originated=graph.session_number,
                last_referenced_turn=graph.turn_number,
            ))
            graph.current_thread = topic

        elif action == "continue":
            for t in graph.open_threads:
                if t.topic == topic:
                    t.times_referenced += 1
                    t.last_referenced_turn = graph.turn_number
            graph.current_thread = topic

        elif action == "close":
            graph.open_threads = [t for t in graph.open_threads if t.topic != topic]
            if graph.current_thread == topic:
                graph.current_thread = None

        elif action == "deflect":
            # Deflection is a signal — mark the thread as tabled
            for t in graph.open_threads:
                if t.topic == topic:
                    t.deliberately_tabled = True
                    t.emotional_weight = min(t.emotional_weight + 0.1, 1.0)

    # ── Log contradictions ──
    contradiction = analysis.get("contradiction_check")
    if contradiction and contradiction.get("confidence", 0) >= 0.5:
        # Check we haven't already logged this one
        existing = [
            c for c in cartographer.contradictions
            if c.dimension == contradiction["dimension"]
        ]
        if not existing:
            cartographer.contradictions.append(Contradiction(
                dimension=contradiction["dimension"],
                stated=contradiction["stated"],
                demonstrated=contradiction["demonstrated"],
                confidence=contradiction["confidence"],
                first_noticed_session=graph.session_number,
            ))

    # ── Store unclassified signals ──
    for signal in _ensure_list(analysis.get("unclassified", [])):
        cartographer.unclassified_signals.append(signal)

    # ── Refresh cartographer needs ──
    cartographer.needs = _compute_needs(cartographer, graph)

    return cartographer, graph


def _compute_needs(cartographer: CartographerState, graph: ConversationGraph) -> List[CartographerNeeds]:
    """
    Determine what the Cartographer still needs, prioritized by
    wellness importance and current confidence gaps.
    """
    needs = []

    # Define wellness importance per dimension
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
            if tc.confidence < 0.7:  # Still need more data
                # Priority = importance * (1 - confidence)
                # High importance + low confidence = highest priority
                priority = importance * (1.0 - tc.confidence)

                # Phase modulation — don't prioritize deep dimensions too early
                if dimension in ("risk_window_pattern", "stressor_signals"):
                    if graph.phase.value < Phase.ATTUNED.value:
                        priority *= 0.4  # Suppress until we're in attuned phase

                needs.append(CartographerNeeds(
                    dimension=dimension,
                    current_confidence=tc.confidence,
                    priority=round(priority, 3),
                ))

    needs.sort(key=lambda n: n.priority, reverse=True)
    return needs


# ─────────────────────────────────────────────
# PHASE TRANSITION ENGINE
# ─────────────────────────────────────────────

def check_phase_transition(graph: ConversationGraph, cartographer: CartographerState) -> Phase:
    """
    Determine if the interviewer should advance to the next phase.
    Phase transitions are based on trust, data confidence, and conversation quality.

    Phases can only move forward, never backward.
    """

    current = graph.phase

    if current == Phase.ARRIVAL:
        # Move to Daily Rhythm when:
        # - Attunement has been established (> 0.2)
        # - At least 5 turns in the conversation
        # - At least 3 core wellness dimensions have some confidence
        core_measured = sum(
            1 for dim in ["mood_baseline", "sleep_pattern", "hunger_relationship",
                          "movement_pattern", "social_pattern"]
            if getattr(cartographer, dim).confidence > 0.15
        )
        if graph.attunement_confidence > 0.2 and graph.turn_number >= 5 and core_measured >= 3:
            return Phase.DAILY_RHYTHM

    elif current == Phase.DAILY_RHYTHM:
        # Move to Attuned when:
        # - Attunement is solid (> 0.45)
        # - At least 10 turns OR session 2+
        # - Response style has some confidence
        # - At least 1 observation has been made
        observations_made = sum(
            1 for _, move in graph.move_history
            if move == MoveType.OBSERVATION
        )
        style_confidence = cartographer.response_style.confidence
        turns_or_sessions = graph.turn_number >= 10 or graph.session_number >= 2
        if (graph.attunement_confidence > 0.45 and turns_or_sessions
                and style_confidence > 0.3 and observations_made >= 1):
            return Phase.ATTUNED

    elif current == Phase.ATTUNED:
        # Move to Companion when:
        # - Attunement is high (> 0.7)
        # - Core wellness dimensions have decent confidence
        core_ready = all(
            getattr(cartographer, dim).confidence > 0.5
            for dim in ["mood_baseline", "hunger_relationship", "sleep_pattern"]
        )
        if graph.attunement_confidence > 0.7 and core_ready:
            return Phase.COMPANION

    return current  # No transition


# ─────────────────────────────────────────────
# TRUST SCORE UPDATE
# ─────────────────────────────────────────────

def update_attunement(
    graph: ConversationGraph,
    analysis: Dict,
) -> float:
    """
    Attunement is earned by:
    - User sharing voluntarily (not just answering questions)
    - User engaging with observations (not deflecting)
    - User returning for more sessions
    - Emotional temperature trending warm

    Attunement is reduced by:
    - Consistent deflection
    - Cold/volatile temperature over multiple turns
    - Long gaps between sessions
    """
    attunement = graph.attunement_confidence

    # Warming temperature builds attunement
    if graph.temperature in (EmotionalTemperature.WARM, EmotionalTemperature.HOT):
        attunement += 0.02
    elif graph.temperature == EmotionalTemperature.COLD:
        attunement -= 0.005

    # Thread engagement builds attunement
    thread_updates = analysis.get("thread_updates", [])
    for tu in thread_updates:
        if tu.get("action") == "continue":
            attunement += 0.01
        elif tu.get("action") == "open":
            attunement += 0.015  # Opening a new topic shows engagement
        elif tu.get("action") == "deflect":
            attunement -= 0.002

    # Session continuity bonus
    if graph.turn_number == 0:  # Start of new session
        attunement += 0.02  # They came back

    # Demonstrated vulnerability spikes
    for signal in analysis.get("trait_signals", []):
        if signal.get("type") == "demonstrated" and signal.get("dimension") in (
            "mood_baseline", "hunger_relationship"
        ):
            attunement += 0.025

    # Base per-turn attunement increment — just showing up and talking earns attunement
    attunement += 0.008

    return max(0.0, min(attunement, 1.0))


# ─────────────────────────────────────────────
# THE MAIN LOOP
# ─────────────────────────────────────────────

class VibSession:
    """
    The main orchestrator. Holds all state and processes turns.

    Usage:
        from interviewer.storage import SoulStorage
        storage = SoulStorage()
        session = VibSession(user_name="Sheltron", llm_client=client, storage=storage)
        result = session.process_turn("I just moved to a new city last month.")
        print(result["response"])
    """

    def __init__(self, user_name: Optional[str] = None, llm_client=None, storage=None):
        self.user_name = user_name
        self.llm_client = llm_client
        self.storage = storage
        self.soul_id = None
        self.session_id = None
        self.max_retries = 2

        # If storage is provided, load or create the soul
        if storage and user_name:
            self.soul_id = storage.get_or_create_soul(user_name)
            soul_data = storage.load_soul(user_name)

            if soul_data and soul_data["session_count"] > 0:
                # Returning user -- restore their soul
                self.cartographer = soul_data["cartographer"]
                self.conversation_history = soul_data["messages"]
                state = storage.load_soul_state(self.soul_id)

                self.graph = ConversationGraph(
                    session_number=soul_data["session_count"],
                    attunement_confidence=state["trust_score"],
                    phase=phase_from_str(state["phase"]),
                    session_start=datetime.now(),
                )
            else:
                # New user
                self.graph = ConversationGraph(session_start=datetime.now())
                self.cartographer = CartographerState()
                self.conversation_history = []

            # Start a new session in the DB
            self.session_id, session_num = storage.start_session(self.soul_id)
            self.graph.session_number = session_num
        else:
            self.graph = ConversationGraph(session_start=datetime.now())
            self.cartographer = CartographerState()
            self.conversation_history = []

        self.cartographer.needs = _compute_needs(self.cartographer, self.graph)

    async def process_turn(self, user_message: str) -> Dict:
        """
        Process a single user message and return the agent's response.
        
        Returns:
            {
                "response": str,           # What the user sees
                "move": SelectedMove,       # Internal: what move was used
                "analysis": dict,           # Internal: cartographer output
                "phase": Phase,             # Internal: current phase
                "validation": dict,         # Internal: response quality check
            }
        """

        # ── Step 0: Record user message ──
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })
        self.graph.turn_number += 1

        # ── Step 1: Cartographer analyzes the message ──
        analysis = await analyze_message(
            user_message=user_message,
            conversation_history=self.conversation_history,
            cartographer=self.cartographer,
            graph=self.graph,
            llm_client=self.llm_client,
        )

        # ── Step 2: Update state from analysis ──
        self.cartographer, self.graph = apply_cartographer_updates(
            analysis, self.cartographer, self.graph
        )

        # ── Step 3: Update attunement ──
        self.graph.attunement_confidence = update_attunement(self.graph, analysis)

        # ── Step 4: Check phase transition ──
        new_phase = check_phase_transition(self.graph, self.cartographer)
        if new_phase != self.graph.phase:
            self.graph.phase = new_phase

        # ── Step 4.5: Check post-binge mode transitions ──
        try:
            from vib_wellness.post_binge import check_mode_transition
            check_mode_transition(self.cartographer)
        except ImportError:
            pass

        # ── Step 5: Select move ──
        move = select_move(self.graph, self.cartographer)

        # ── Step 6: Build prompt ──
        prompt = build_prompt(
            move=move,
            graph=self.graph,
            cartographer=self.cartographer,
            conversation_history=self.conversation_history,
            user_name=self.user_name,
        )

        # ── Step 7: Generate response (with retry on validation failure) ──
        response_text = None
        validation = None

        for attempt in range(self.max_retries + 1):
            if self.llm_client:
                response_text = await self.llm_client.interviewer_generate(
                    system=prompt["system"],
                    messages=prompt["messages"],
                )
            else:
                response_text = f"[{move.move_type.value}] — {move.prompt_context[:100]}..."
                break

            # ── Step 8: Validate response ──
            validation = validate_response(response_text, move, self.graph)

            if validation["valid"]:
                break
            elif attempt < self.max_retries:
                # Add a correction instruction and retry
                prompt["messages"].append({
                    "role": "assistant",
                    "content": response_text,
                })
                prompt["messages"].append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM: Response violated constraints: {validation['issues']}. "
                        f"Regenerate following the rules exactly. "
                        f"{'Keep to 1-2 sentences max.' if move.move_type == MoveType.REST else 'Keep to 1-4 sentences.'} "
                        f"{'Do not ask questions.' if move.move_type == MoveType.REST else 'Ask at most 1 question.'}"
                    ),
                })
            # else: accept the response even if imperfect — better than no response

        # ── Step 9: Record agent response ──
        self.conversation_history.append({
            "role": "assistant",
            "content": response_text,
        })

        # ── Step 10: Update move history ──
        self.graph.move_history.append((self.graph.turn_number, move.move_type))

        # ── Step 11: Persist to storage ──
        if self.storage and self.soul_id and self.session_id:
            self._persist_turn(user_message, response_text, analysis)

        return {
            "response": response_text,
            "move": move,
            "analysis": analysis,
            "phase": self.graph.phase,
            "validation": validation,
        }

    def _persist_turn(self, user_message: str, response_text: str, analysis: Dict):
        """Save everything from this turn to persistent storage."""
        s = self.storage

        # Save messages
        s.save_message(self.soul_id, self.session_id,
                       self.graph.turn_number, "user", user_message)
        s.save_message(self.soul_id, self.session_id,
                       self.graph.turn_number, "assistant", response_text)

        # Save trait evidence (with the user's actual words)
        signals = analysis.get("trait_signals", [])
        if isinstance(signals, dict):
            signals = [signals]
        if signals:
            s.save_evidence(self.soul_id, self.session_id,
                            self.graph.turn_number, signals, user_message)

        # Save contradictions
        contradiction = analysis.get("contradiction_check")
        if contradiction and contradiction.get("confidence", 0) >= 0.5:
            s.save_contradiction(self.soul_id, {
                "dimension": contradiction["dimension"],
                "stated": contradiction["stated"],
                "demonstrated": contradiction["demonstrated"],
                "confidence": contradiction["confidence"],
                "first_noticed_session": self.graph.session_number,
            })

        # Save soul state (attunement + phase)
        s.save_soul_state(self.soul_id, self.graph.attunement_confidence,
                          self.graph.phase.name)

    def start_new_session(self):
        """Called when the user returns for a new conversation."""
        self.graph.session_number += 1
        self.graph.turn_number = 0
        self.graph.session_start = datetime.now()
        self.graph.move_history = []  # Reset per-session tracking
        self.graph.energy_level = 0.6  # Fresh session energy
        self.graph.temperature = EmotionalTemperature.COOL  # Reset — don't assume

    def get_soul_readiness(self) -> Dict:
        """
        How ready is this user's Soul for wellness attunement?
        Returns a readiness report.
        """
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
