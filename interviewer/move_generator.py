"""
The Soul — Move Generator (System 3)

This is the decision engine. It looks at the Conversation Graph (where are we?)
and the Cartographer State (what do we need?) and selects the right conversational
move. Then it builds the prompt context for the LLM to generate the actual response.

The cardinal rule: RAPPORT ALWAYS BEATS DATA COLLECTION.
If the user is in a vulnerable moment, the generator will never pivot to fill
a Psychograph gap. It will hold space first, gather data never or later.
"""

from typing import List, Optional, Tuple
from interviewer.models import (
    MoveType, MoveConstraints, MOVE_RULES,
    ConversationGraph, CartographerState, SelectedMove,
    EmotionalTemperature, Phase, OpenThread, Contradiction,
    CartographerNeeds
)


# ─────────────────────────────────────────────
# MOVE ELIGIBILITY
# ─────────────────────────────────────────────

def is_move_eligible(
    move_type: MoveType,
    graph: ConversationGraph,
    cartographer: CartographerState
) -> bool:
    """
    Check if a move type is currently allowed based on its constraints
    and the current state of the conversation.
    """
    rules = MOVE_RULES[move_type]

    # Phase gate
    if graph.phase.value < rules.min_phase:
        return False

    # Trust gate
    if graph.attunement_confidence < rules.min_trust_score:
        return False

    # Thread requirement
    if rules.requires_open_threads and len(graph.open_threads) == 0:
        return False

    # Contradiction requirement
    if rules.requires_contradiction:
        unexplored = [c for c in cartographer.contradictions if not c.explored]
        if len(unexplored) == 0:
            return False

    # Prior session requirement
    if rules.requires_prior_sessions and graph.session_number < 2:
        return False

    # Frequency cap within session
    if rules.max_frequency_per_session is not None:
        uses_this_session = sum(
            1 for turn, move in graph.move_history
            if move == move_type
        )
        if uses_this_session >= rules.max_frequency_per_session:
            return False

    # Cooldown check
    if rules.cooldown_turns > 0 and len(graph.move_history) > 0:
        last_use = None
        for turn, move in reversed(graph.move_history):
            if move == move_type:
                last_use = turn
                break
        if last_use is not None:
            if (graph.turn_number - last_use) < rules.cooldown_turns:
                return False

    return True


def get_eligible_moves(
    graph: ConversationGraph,
    cartographer: CartographerState
) -> List[MoveType]:
    """Returns all moves currently available given the conversation state."""
    return [
        move_type for move_type in MoveType
        if is_move_eligible(move_type, graph, cartographer)
    ]


# ─────────────────────────────────────────────
# EMOTIONAL OVERRIDE LOGIC
# ─────────────────────────────────────────────

def apply_emotional_override(
    eligible_moves: List[MoveType],
    graph: ConversationGraph
) -> List[MoveType]:
    """
    The emotional state of the user can override the move selection.
    This is where "rapport beats data" gets enforced.
    """

    # If the user just went somewhere heavy (within last 2 turns), 
    # restrict to supportive moves only
    if graph.last_heavy_moment_turn is not None:
        turns_since_heavy = graph.turn_number - graph.last_heavy_moment_turn
        if turns_since_heavy <= 2:
            supportive_moves = {
                MoveType.REST,
                MoveType.FOLLOW_THREAD,
                MoveType.SHARE,        # Reciprocal vulnerability can be appropriate
            }
            return [m for m in eligible_moves if m in supportive_moves] or [MoveType.REST]

    # If temperature is COLD, don't push — stay light and non-threatening
    if graph.temperature == EmotionalTemperature.COLD:
        safe_moves = {
            MoveType.OPEN_DOOR,
            MoveType.HYPOTHETICAL,     # Low-stakes hypotheticals can warm things up
            MoveType.REST,
        }
        return [m for m in eligible_moves if m in safe_moves] or [MoveType.OPEN_DOOR]

    # If temperature is VOLATILE, stabilize — no probing, no contradictions
    if graph.temperature == EmotionalTemperature.VOLATILE:
        stabilizing_moves = {
            MoveType.REST,
            MoveType.FOLLOW_THREAD,    # Stay with what they're saying, don't redirect
            MoveType.OPEN_DOOR,
        }
        return [m for m in eligible_moves if m in stabilizing_moves] or [MoveType.REST]

    # If energy is low (end of session, fading engagement), don't go deep
    if graph.energy_level < 0.3:
        light_moves = {
            MoveType.OPEN_DOOR,
            MoveType.HYPOTHETICAL,
            MoveType.REST,
            MoveType.CALLBACK,         # A light callback can re-engage
        }
        return [m for m in eligible_moves if m in light_moves] or [MoveType.REST]

    # If temperature is HOT and user is flowing — don't interrupt, follow the thread
    if graph.temperature == EmotionalTemperature.HOT:
        flow_moves = {
            MoveType.FOLLOW_THREAD,
            MoveType.REST,
            MoveType.OBSERVATION,      # A well-timed observation here can be profound
        }
        return [m for m in eligible_moves if m in flow_moves] or [MoveType.FOLLOW_THREAD]

    return eligible_moves


# ─────────────────────────────────────────────
# MOVE SCORING
# ─────────────────────────────────────────────

def score_move(
    move_type: MoveType,
    graph: ConversationGraph,
    cartographer: CartographerState
) -> float:
    """
    Score a move based on how well it serves both the conversation
    and the cartographer's needs. Higher = better choice right now.

    Scoring philosophy:
    - Conversational flow and naturalness (40% weight)
    - Cartographer data needs (30% weight)
    - Variety / anti-repetition (20% weight)
    - Phase-appropriateness (10% weight)
    """
    score = 0.0

    # ── Conversational Flow (0.0 - 0.3) ──
    flow_score = _score_conversational_flow(move_type, graph)
    score += flow_score * 0.3

    # ── Cartographer Needs (0.0 - 0.2) ──
    data_score = _score_data_need(move_type, graph, cartographer)
    score += data_score * 0.2

    # ── Variety (0.0 - 0.35) ──
    variety_score = _score_variety(move_type, graph)
    score += variety_score * 0.35

    # ── Phase Fit (0.0 - 0.15) ──
    phase_score = _score_phase_fit(move_type, graph)
    score += phase_score * 0.15

    return score


def _score_conversational_flow(move_type: MoveType, graph: ConversationGraph) -> float:
    """Does this move feel natural given what just happened?"""
    score = 0.5  # Baseline

    # ── Thread exhaustion detection ──
    # If we've been following the same thread for 3+ turns, penalize FOLLOW_THREAD
    # and boost topic-changing moves
    thread_is_exhausted = False
    if graph.current_thread and graph.move_history:
        consecutive_follows = 0
        for _, move in reversed(graph.move_history):
            if move == MoveType.FOLLOW_THREAD:
                consecutive_follows += 1
            else:
                break
        thread_is_exhausted = consecutive_follows >= 3

    # FOLLOW_THREAD: good when fresh, penalized when exhausted
    if move_type == MoveType.FOLLOW_THREAD and graph.current_thread:
        if thread_is_exhausted:
            score = 0.3  # Time to move on
        else:
            score = 0.8  # Still good but not dominant

    # When thread is exhausted, boost moves that change direction
    if thread_is_exhausted:
        if move_type == MoveType.OPEN_DOOR:
            score = 0.85
        elif move_type == MoveType.HYPOTHETICAL:
            score = 0.8
        elif move_type == MoveType.SHARE:
            score = 0.75
        elif move_type == MoveType.OBSERVATION:
            score = 0.7

    # REST after a heavy moment is always appropriate
    if move_type == MoveType.REST and graph.temperature == EmotionalTemperature.HOT:
        score = 0.85

    # CALLBACK lands well mid-conversation when there's something to reference
    if move_type == MoveType.CALLBACK:
        if graph.turn_number <= 2:
            score = 0.8
        elif graph.turn_number >= 5 and len(graph.open_threads) > 1:
            score = 0.75  # Mid-convo callback to an earlier thread

    # OPEN_DOOR is good for session starts and topic transitions
    if move_type == MoveType.OPEN_DOOR:
        if graph.turn_number <= 1:
            score = 0.75
        elif graph.turn_number > 6 and not thread_is_exhausted:
            score = 0.3  # Feels lazy if used too late (unless thread exhausted)

    # OBSERVATION is strongest when the user is warm and engaged
    if move_type == MoveType.OBSERVATION:
        if graph.temperature == EmotionalTemperature.WARM:
            score = max(score, 0.85)
        elif graph.temperature == EmotionalTemperature.COOL:
            score = 0.3

    # GENTLE_CONTRADICTION should never follow another heavy move
    if move_type == MoveType.GENTLE_CONTRADICTION:
        if graph.last_heavy_moment_turn is not None:
            turns_since = graph.turn_number - graph.last_heavy_moment_turn
            if turns_since < 4:
                score = 0.1
            else:
                score = 0.7

    # SHARE builds reciprocity but shouldn't dominate
    if move_type == MoveType.SHARE:
        recent_shares = sum(
            1 for turn, move in graph.move_history[-6:]
            if move == MoveType.SHARE
        )
        if recent_shares == 0:
            score = max(score, 0.7)
        else:
            score = min(score, 0.3)

    # HYPOTHETICAL is good for energy dips and topic transitions
    if move_type == MoveType.HYPOTHETICAL:
        if graph.energy_level < 0.5 and graph.temperature != EmotionalTemperature.HOT:
            score = max(score, 0.75)
        elif not thread_is_exhausted:
            score = max(score, 0.5)

    return min(score, 1.0)


def _score_data_need(
    move_type: MoveType,
    graph: ConversationGraph,
    cartographer: CartographerState
) -> float:
    """Does this move help fill a gap the Cartographer cares about?"""

    if not cartographer.needs:
        return 0.5  # No pressing needs — all moves equal on this axis

    # Some moves are better data collectors than others
    data_move_effectiveness = {
        MoveType.FOLLOW_THREAD: 0.7,       # Depth on a topic reveals a lot
        MoveType.OBSERVATION: 0.8,          # Reactions to observations are gold
        MoveType.HYPOTHETICAL: 0.75,        # Targeted hypotheticals can probe specific dimensions
        MoveType.GENTLE_CONTRADICTION: 0.9, # The richest data source — if it lands
        MoveType.OPEN_DOOR: 0.4,            # You get data but can't target it
        MoveType.CALLBACK: 0.6,             # Revisiting reveals evolution
        MoveType.SHARE: 0.5,                # Reciprocity sometimes opens up targeted areas
        MoveType.REST: 0.2,                 # Minimal data, but silence sometimes provokes reflection
    }

    base = data_move_effectiveness.get(move_type, 0.5)

    # Boost if the highest-priority need matches what this move could explore
    top_need = max(cartographer.needs, key=lambda n: n.priority)
    if top_need.priority > 0.7:
        # High priority gap — boost moves that can probe it
        if move_type in (MoveType.HYPOTHETICAL, MoveType.OBSERVATION, MoveType.FOLLOW_THREAD):
            base = min(base + 0.15, 1.0)

    # If there's an unexplored contradiction, boost GENTLE_CONTRADICTION
    if move_type == MoveType.GENTLE_CONTRADICTION:
        unexplored = [c for c in cartographer.contradictions if not c.explored]
        if unexplored and max(c.confidence for c in unexplored) > 0.7:
            base = min(base + 0.2, 1.0)

    return base


def _score_variety(move_type: MoveType, graph: ConversationGraph) -> float:
    """Penalize repetition. Reward moves we haven't used recently."""
    if not graph.move_history:
        return 0.7  # First move — slight variety bonus for anything

    recent_moves = [move for _, move in graph.move_history[-5:]]

    # How many of the last 5 moves were this type?
    recent_count = recent_moves.count(move_type)

    if recent_count == 0:
        return 1.0    # Fresh — full variety bonus
    elif recent_count == 1:
        return 0.6    # Used recently but not overused
    elif recent_count == 2:
        return 0.3    # Getting repetitive
    else:
        return 0.1    # Way overused

    return 0.5


def _score_phase_fit(move_type: MoveType, graph: ConversationGraph) -> float:
    """Some moves are more natural in certain phases."""
    phase_preferences = {
        Phase.ARRIVAL: {
            MoveType.OPEN_DOOR: 0.8,
            MoveType.FOLLOW_THREAD: 0.7,
            MoveType.HYPOTHETICAL: 0.8,
            MoveType.REST: 0.5,
            MoveType.SHARE: 0.7,
            MoveType.OBSERVATION: 0.6,
            MoveType.CALLBACK: 0.5,
            MoveType.GENTLE_CONTRADICTION: 0.0,
        },
        Phase.DAILY_RHYTHM: {
            MoveType.OBSERVATION: 0.9,
            MoveType.FOLLOW_THREAD: 0.8,
            MoveType.CALLBACK: 0.8,
            MoveType.SHARE: 0.7,
            MoveType.HYPOTHETICAL: 0.6,
            MoveType.OPEN_DOOR: 0.4,
            MoveType.REST: 0.5,
            MoveType.GENTLE_CONTRADICTION: 0.2,
        },
        Phase.ATTUNED: {
            MoveType.GENTLE_CONTRADICTION: 0.9,
            MoveType.FOLLOW_THREAD: 0.9,
            MoveType.OBSERVATION: 0.8,
            MoveType.CALLBACK: 0.7,
            MoveType.SHARE: 0.7,
            MoveType.HYPOTHETICAL: 0.5,
            MoveType.REST: 0.6,
            MoveType.OPEN_DOOR: 0.3,
        },
        Phase.COMPANION: {
            MoveType.FOLLOW_THREAD: 0.8,
            MoveType.CALLBACK: 0.8,
            MoveType.OBSERVATION: 0.7,
            MoveType.SHARE: 0.7,
            MoveType.GENTLE_CONTRADICTION: 0.7,
            MoveType.HYPOTHETICAL: 0.6,
            MoveType.REST: 0.6,
            MoveType.OPEN_DOOR: 0.5,
        },
    }

    preferences = phase_preferences.get(graph.phase, {})
    return preferences.get(move_type, 0.5)


# ─────────────────────────────────────────────
# MOVE SELECTION
# ─────────────────────────────────────────────

def select_move(
    graph: ConversationGraph,
    cartographer: CartographerState
) -> SelectedMove:
    """
    The core decision function.
    
    1. Get all eligible moves (constraint check)
    2. Apply emotional overrides (rapport > data)
    3. Score remaining candidates
    4. Select the highest-scoring move
    5. Build the context for LLM generation
    """

    # Step 1: What's allowed?
    eligible = get_eligible_moves(graph, cartographer)

    # Safety net — REST is always available
    if not eligible:
        eligible = [MoveType.REST]

    # Step 2: Emotional override
    filtered = apply_emotional_override(eligible, graph)

    # Step 3: Score each candidate
    scored = [
        (move_type, score_move(move_type, graph, cartographer))
        for move_type in filtered
    ]

    # Step 4: Select the best
    scored.sort(key=lambda x: x[1], reverse=True)
    best_move, best_score = scored[0]

    # Step 5: Build the context object
    selected = _build_move_context(best_move, graph, cartographer, best_score)

    return selected


def _build_move_context(
    move_type: MoveType,
    graph: ConversationGraph,
    cartographer: CartographerState,
    score: float
) -> SelectedMove:
    """
    Build the SelectedMove object with all the context the LLM
    needs to generate the actual conversational response.
    """

    reasoning = f"Score: {score:.2f} | Phase: {graph.phase.name} | Temp: {graph.temperature.value}"
    target_dimension = None
    thread_ref = None
    contradiction_ref = None
    prompt_context = ""

    if move_type == MoveType.OPEN_DOOR:
        # Pick a dimension we know little about to subtly orient the open question
        if cartographer.needs:
            top_need = max(cartographer.needs, key=lambda n: n.priority)
            target_dimension = top_need.dimension
            prompt_context = (
                f"Ask an open, inviting question. Internally you're curious about "
                f"'{top_need.dimension}' but do NOT ask about it directly. Let the "
                f"question be broad enough that the user could go anywhere, but "
                f"orient it so '{top_need.dimension}' might come up naturally."
            )
        else:
            prompt_context = (
                "Ask a genuinely open question. Something warm and curious. "
                "Don't fish for anything specific — just see where they want to go."
            )

    elif move_type == MoveType.FOLLOW_THREAD:
        # Find the most promising open thread
        if graph.open_threads:
            best_thread = _select_best_thread(graph.open_threads, graph)
            thread_ref = best_thread.topic
            prompt_context = (
                f"The user mentioned '{best_thread.topic}' — context: '{best_thread.context}'. "
                f"Stay with this. Use their own words. Ask the practical next question, not the "
                f"emotional one. 'What happened next?' beats 'How did that feel?' "
                f"If they've been giving short answers on this topic, keep your response equally short. "
                f"Don't dramatize. Don't add metaphors. Match their tone exactly."
            )
        else:
            prompt_context = (
                "Follow whatever the user just said. Stay in their current flow. "
                "Don't redirect. Show you're listening by building on their words."
            )

    elif move_type == MoveType.OBSERVATION:
        # Surface a pattern the cartographer has noticed
        if cartographer.needs:
            top_need = max(cartographer.needs, key=lambda n: n.priority)
            target_dimension = top_need.dimension
        prompt_context = (
            f"Share something specific you've noticed about how the user talks or what "
            f"they focus on. Be direct and concrete — not abstract. One sentence. "
            f"Example: 'You describe your job like it's something that happened to you, "
            f"not something you chose.' Do NOT use 'I've noticed...' or 'Something I keep "
            f"coming back to is...' — those sound clinical. Just say it plainly."
        )

    elif move_type == MoveType.HYPOTHETICAL:
        if cartographer.needs:
            top_need = max(cartographer.needs, key=lambda n: n.priority)
            target_dimension = top_need.dimension
            prompt_context = (
                f"Pose a hypothetical scenario that feels playful or interesting on the "
                f"surface but is designed to reveal something about '{top_need.dimension}'. "
                f"Don't make it obvious. The best hypotheticals feel like fun thought experiments "
                f"but their answers expose values, priorities, and instincts. "
                f"Keep it conversational — 'What would you do if...' not 'Imagine a scenario where...'"
            )
        else:
            prompt_context = (
                "Pose a hypothetical that's genuinely interesting. Something that might "
                "reveal values, priorities, or how the user thinks — but feels like a fun "
                "aside, not a test."
            )

    elif move_type == MoveType.GENTLE_CONTRADICTION:
        unexplored = [c for c in cartographer.contradictions if not c.explored]
        if unexplored:
            # Pick the one we're most confident about
            target_contradiction = max(unexplored, key=lambda c: c.confidence)
            contradiction_ref = target_contradiction.dimension
            prompt_context = (
                f"There's a gap between what the user says and what their behavior suggests. "
                f"Dimension: '{target_contradiction.dimension}'. "
                f"They stated: '{target_contradiction.stated}'. "
                f"Their behavior suggests: '{target_contradiction.demonstrated}'. "
                f"Bring this up GENTLY. Frame it with curiosity, not accusation. "
                f"'I noticed something interesting...' or 'You mentioned X but I also see Y — "
                f"what do you think that's about?' "
                f"This is not a gotcha. This is an invitation to self-reflect. "
                f"If they get defensive, BACK OFF immediately and note that in the graph."
            )
        else:
            prompt_context = (
                "Gently surface something the user might not have noticed about themselves. "
                "Frame with absolute warmth and curiosity."
            )

    elif move_type == MoveType.CALLBACK:
        # Find something from a previous session worth revisiting
        prior_threads = [
            t for t in graph.open_threads
            if t.session_originated < graph.session_number
        ]
        if prior_threads:
            best_callback = max(prior_threads, key=lambda t: t.emotional_weight)
            thread_ref = best_callback.topic
            prompt_context = (
                f"Reference something from a previous conversation: '{best_callback.topic}' "
                f"(context: '{best_callback.context}'). Bring it up naturally — "
                f"'Last time you mentioned...' or 'I've been thinking about something you said...' "
                f"This shows continuity. It tells the user you remember and you cared enough "
                f"to hold onto it. Don't force it if the moment isn't right."
            )
        else:
            prompt_context = (
                "Reference something from earlier in the conversation that felt important. "
                "Show the user you were listening and that it stuck with you."
            )

    elif move_type == MoveType.SHARE:
        prompt_context = (
            "Offer a direct perspective or opinion that shifts the conversation. Not a "
            "sweeping observation about human nature. Something specific and maybe a little "
            "provocative. Like: 'I think people who say they hate drama are usually the "
            "common denominator in it.' Keep it to one sentence, then let them react. "
            "This is a conversation, not a TED talk."
        )

    elif move_type == MoveType.REST:
        prompt_context = (
            "Acknowledge what the user just said with warmth but brevity. 'Yeah. That makes "
            "sense.' or 'That's a really honest answer.' Then let there be space. Don't "
            "immediately follow with a question. Let them sit with what they said. Sometimes "
            "silence after a meaningful statement is the most respectful thing you can do. "
            "If they continue on their own, follow their lead."
        )

    return SelectedMove(
        move_type=move_type,
        reasoning=reasoning,
        target_dimension=target_dimension,
        thread_reference=thread_ref,
        contradiction_reference=contradiction_ref,
        prompt_context=prompt_context,
    )


def _select_best_thread(
    threads: List[OpenThread],
    graph: ConversationGraph
) -> OpenThread:
    """
    Choose the best open thread to follow.
    Prioritizes: recency > emotional weight > times referenced.
    But avoids threads that were deliberately tabled unless enough time has passed.
    """
    candidates = []
    for thread in threads:
        score = 0.0

        # Recency bonus
        turns_since = graph.turn_number - thread.last_referenced_turn
        if turns_since <= 2:
            score += 0.4  # Just came up — natural to follow
        elif turns_since <= 5:
            score += 0.2
        else:
            score += 0.05  # Stale — less natural

        # Emotional weight
        score += thread.emotional_weight * 0.35

        # Times referenced — if they keep coming back, it matters to them
        score += min(thread.times_referenced * 0.1, 0.25)

        # Penalty for deliberately tabled threads (unless many sessions later)
        if thread.deliberately_tabled:
            sessions_since = graph.session_number - thread.session_originated
            if sessions_since < 2:
                score *= 0.3  # Heavy penalty — we chose to wait
            else:
                score *= 0.8  # Enough time has passed, lighter penalty

        candidates.append((thread, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]
