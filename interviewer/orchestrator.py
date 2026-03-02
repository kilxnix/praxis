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
    OpenThread, TraitConfidence, Contradiction, CartographerNeeds,
    MoveType, SelectedMove
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

CARTOGRAPHER_SYSTEM_PROMPT = """You are the Soul Cartographer — an analytical system that observes 
human conversation and maps personality dimensions.

You receive a user message and the current state of what you know about them.
You output structured updates ONLY. You do not generate conversation.

For each message, analyze:

1. TRAIT_SIGNALS: What personality dimensions does this message inform?
   Format: {"dimension": str, "signal": str, "direction": float (-1.0 to 1.0), 
            "confidence_delta": float (0.0 to 0.1), "type": "stated"|"demonstrated"}
   - "stated" = the user explicitly said something about themselves
   - "demonstrated" = their behavior/language implies it (more reliable)

2. EMOTIONAL_READ: What's the emotional temperature of this message?
   Format: {"temperature": "cold"|"cool"|"warm"|"hot"|"volatile", 
            "trend": "warming"|"cooling"|"stable"|"volatile",
            "energy": float (0.0 to 1.0)}

3. THREAD_UPDATES: Did they open a new topic? Return to an old one? Close one?
   Format: {"action": "open"|"continue"|"close"|"deflect", 
            "topic": str, "context": str, "emotional_weight": float}
   - "deflect" means they were asked about something and changed the subject.
     This is significant data — the avoidance itself is a signal.

4. CONTRADICTION_CHECK: Does anything in this message conflict with prior observations?
   Format: {"dimension": str, "stated": str, "demonstrated": str, 
            "confidence": float} or null

5. UNCLASSIFIED: Anything notable that doesn't fit the above categories.
   A phrase, a pattern, a vibe. Store it for later pattern matching.

RULES:
- Be conservative with confidence_delta. A single message rarely shifts confidence 
  more than 0.05. Patterns over multiple sessions shift it 0.1.
- "Demonstrated" signals are worth 2x "stated" signals for confidence.
- Contradictions need at least 0.5 confidence before logging. Don't flag 
  normal human inconsistency — only meaningful gaps.
- Not every message has signals for every dimension. Return empty lists 
  where nothing was observed. Don't hallucinate patterns.

Respond ONLY with valid JSON matching the schema above.
"""


def analyze_message(
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
        return llm_client.cartographer_analyze(
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
    traits = {}
    for dimension in [
        "openness", "conscientiousness", "extroversion",
        "agreeableness", "neuroticism", "attachment_style",
        "conflict_style", "communication_style",
        "vulnerability_comfort", "independence_interdependence"
    ]:
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
    for signal in analysis.get("trait_signals", []):
        dimension = signal.get("dimension", "")
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, TraitConfidence):
            # Apply confidence delta — demonstrated signals are worth more
            delta = signal.get("confidence_delta", 0.0)
            if signal.get("type") == "demonstrated":
                delta *= 2.0
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
    for thread_update in analysis.get("thread_updates", []):
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
    for signal in analysis.get("unclassified", []):
        cartographer.unclassified_signals.append(signal)

    # ── Refresh cartographer needs ──
    cartographer.needs = _compute_needs(cartographer, graph)

    return cartographer, graph


def _compute_needs(cartographer: CartographerState, graph: ConversationGraph) -> List[CartographerNeeds]:
    """
    Determine what the Cartographer still needs, prioritized by
    importance for matching and current confidence gaps.
    """
    needs = []

    # Define matching importance per dimension
    matching_importance = {
        "attachment_style": 0.95,          # Critical for relationship success
        "conflict_style": 0.9,             # How fights go determines everything
        "communication_style": 0.85,       # Day-to-day compatibility
        "vulnerability_comfort": 0.8,      # Emotional intimacy capacity
        "independence_interdependence": 0.8,
        "openness": 0.7,
        "neuroticism": 0.7,
        "conscientiousness": 0.6,
        "extroversion": 0.6,
        "agreeableness": 0.55,
    }

    for dimension, importance in matching_importance.items():
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, TraitConfidence):
            if tc.confidence < 0.7:  # Still need more data
                # Priority = importance * (1 - confidence)
                # High importance + low confidence = highest priority
                priority = importance * (1.0 - tc.confidence)

                # Phase modulation — don't prioritize deep dimensions too early
                if dimension in ("attachment_style", "conflict_style", "vulnerability_comfort"):
                    if graph.phase.value < Phase.DEPTH.value:
                        priority *= 0.4  # Suppress until we're in depth phase

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
    Phase transitions are based on trust, data confidence, and session count.
    
    Phases can only move forward, never backward.
    """

    current = graph.phase

    if current == Phase.FIRST_CONTACT:
        # Move to Pattern Recognition when:
        # - Trust has been established (> 0.25)
        # - At least 2 sessions completed
        # - At least 3 OCEAN traits have some confidence
        ocean_measured = sum(
            1 for dim in ["openness", "conscientiousness", "extroversion", "agreeableness", "neuroticism"]
            if getattr(cartographer, dim).confidence > 0.15
        )
        if graph.trust_score > 0.25 and graph.session_number >= 2 and ocean_measured >= 3:
            return Phase.PATTERN_RECOGNITION

    elif current == Phase.PATTERN_RECOGNITION:
        # Move to Depth when:
        # - Trust is solid (> 0.5)
        # - At least 4 sessions
        # - Communication style is mapped
        # - At least 1 observation has been delivered and received well
        observations_made = sum(
            1 for _, move in graph.move_history
            if move == MoveType.OBSERVATION
        )
        comm_confidence = cartographer.communication_style.confidence
        if (graph.trust_score > 0.5 and graph.session_number >= 4
                and comm_confidence > 0.4 and observations_made >= 2):
            return Phase.DEPTH

    elif current == Phase.DEPTH:
        # Move to Ongoing when:
        # - Trust is high (> 0.75)
        # - Core matching dimensions have good confidence
        # - The soul is "matchable"
        core_ready = all(
            getattr(cartographer, dim).confidence > 0.6
            for dim in ["attachment_style", "conflict_style", "communication_style"]
        )
        if graph.trust_score > 0.75 and core_ready:
            return Phase.ONGOING

    return current  # No transition


# ─────────────────────────────────────────────
# TRUST SCORE UPDATE
# ─────────────────────────────────────────────

def update_trust_score(
    graph: ConversationGraph,
    analysis: Dict,
) -> float:
    """
    Trust is earned by:
    - User sharing voluntarily (not just answering questions)
    - User engaging with observations (not deflecting)
    - User returning for more sessions
    - Emotional temperature trending warm
    
    Trust is reduced by:
    - Consistent deflection
    - Cold/volatile temperature over multiple turns
    - Long gaps between sessions
    """
    trust = graph.trust_score

    # Warming temperature builds trust
    if graph.temperature in (EmotionalTemperature.WARM, EmotionalTemperature.HOT):
        trust += 0.01
    elif graph.temperature == EmotionalTemperature.COLD:
        trust -= 0.005

    # Thread engagement builds trust
    thread_updates = analysis.get("thread_updates", [])
    for tu in thread_updates:
        if tu.get("action") == "continue":
            trust += 0.005  # They're engaging, not deflecting
        elif tu.get("action") == "deflect":
            trust -= 0.002  # Slight reduction — deflection is normal but slows trust

    # Session continuity bonus
    if graph.turn_number == 0:  # Start of new session
        trust += 0.02  # They came back

    # Demonstrated vulnerability spikes
    for signal in analysis.get("trait_signals", []):
        if signal.get("type") == "demonstrated" and signal.get("dimension") in (
            "vulnerability_comfort", "attachment_style"
        ):
            trust += 0.015  # They showed something real

    return max(0.0, min(trust, 1.0))


# ─────────────────────────────────────────────
# THE MAIN LOOP
# ─────────────────────────────────────────────

class InterviewerSession:
    """
    The main orchestrator. Holds all state and processes turns.
    
    Usage:
        from llm_client import SoulLLMClient
        client = SoulLLMClient(api_key="sk-ant-...")
        session = InterviewerSession(user_name="Sheltron", llm_client=client)
        result = session.process_turn("I just moved to a new city last month.")
        print(result["response"])
    """

    def __init__(self, user_name: Optional[str] = None, llm_client=None):
        self.user_name = user_name
        self.llm_client = llm_client
        self.graph = ConversationGraph(session_start=datetime.now())
        self.cartographer = CartographerState()
        self.conversation_history: List[Dict[str, str]] = []
        self.max_retries = 2  # Retry failed validations

        # Initialize cartographer needs with everything at zero
        self.cartographer.needs = _compute_needs(self.cartographer, self.graph)

    def process_turn(self, user_message: str) -> Dict:
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
        analysis = analyze_message(
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

        # ── Step 3: Update trust ──
        self.graph.trust_score = update_trust_score(self.graph, analysis)

        # ── Step 4: Check phase transition ──
        new_phase = check_phase_transition(self.graph, self.cartographer)
        if new_phase != self.graph.phase:
            self.graph.phase = new_phase

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
                response_text = self.llm_client.interviewer_generate(
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

        return {
            "response": response_text,
            "move": move,
            "analysis": analysis,
            "phase": self.graph.phase,
            "validation": validation,
        }

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
        How ready is this user's Soul for matching?
        Returns a readiness report.
        """
        dimensions = {
            "attachment_style": self.cartographer.attachment_style.confidence,
            "conflict_style": self.cartographer.conflict_style.confidence,
            "communication_style": self.cartographer.communication_style.confidence,
            "vulnerability_comfort": self.cartographer.vulnerability_comfort.confidence,
            "independence_interdependence": self.cartographer.independence_interdependence.confidence,
            "openness": self.cartographer.openness.confidence,
            "conscientiousness": self.cartographer.conscientiousness.confidence,
            "extroversion": self.cartographer.extroversion.confidence,
            "agreeableness": self.cartographer.agreeableness.confidence,
            "neuroticism": self.cartographer.neuroticism.confidence,
        }

        avg_confidence = sum(dimensions.values()) / len(dimensions)
        core_ready = all(
            dimensions[d] > 0.6
            for d in ["attachment_style", "conflict_style", "communication_style"]
        )

        return {
            "overall_confidence": round(avg_confidence, 2),
            "core_dimensions_ready": core_ready,
            "matchable": core_ready and avg_confidence > 0.5,
            "dimensions": dimensions,
            "sessions_completed": self.graph.session_number,
            "phase": self.graph.phase.name,
            "trust_level": round(self.graph.trust_score, 2),
            "open_contradictions": len([
                c for c in self.cartographer.contradictions if not c.explored
            ]),
        }
