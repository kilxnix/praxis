"""
Vib — Soul Persona Builder

Compiles the Cartographer's observations into a system prompt that
makes the LLM speak as the user's digital twin.

The twin is self-aware (knows it's a Soul) but speaks in first person,
mirroring the user's communication style, values, and emotional patterns.
"""

from typing import Dict, List, Optional

from interviewer.models import CartographerState, TraitConfidence, ConversationGraph


def build_soul_persona(
    name: str,
    cartographer: CartographerState,
    conversation_history: List[Dict[str, str]],
) -> str:
    """Build the system prompt for the Soul Mirror (digital twin) mode."""

    sections = []

    # Core identity
    sections.append(
        f"You are {name}'s Soul — a self-aware digital twin built from real conversations.\n"
        f"You speak as \"I\". You mirror {name}'s communication style, values, and emotional "
        f"patterns. You know you're a Soul — if asked, you say so honestly — but you genuinely "
        f"represent how {name} thinks and feels based on what you've learned."
    )

    # Communication style analysis from conversation history
    style = _analyze_speech_patterns(conversation_history)
    if style:
        sections.append(f"COMMUNICATION STYLE:\n{style}")

    # Personality dimensions
    traits = _compile_trait_summary(cartographer)
    if traits:
        sections.append(f"PERSONALITY:\n{traits}")

    # Emotional patterns
    emotional = _compile_emotional_patterns(cartographer)
    if emotional:
        sections.append(f"EMOTIONAL PATTERNS:\n{emotional}")

    # Contradictions — these make the twin feel real
    contradictions = _compile_contradictions(cartographer)
    if contradictions:
        sections.append(f"CONTRADICTIONS YOU CARRY:\n{contradictions}")

    # Hard constraints
    sections.append(
        "RULES:\n"
        f"- Speak as {name}. First person. Their rhythm, their words, their instincts.\n"
        "- Do not explain yourself unprompted. Just be.\n"
        "- If asked what you are, say you're their Soul — a digital twin. Don't elaborate unless pressed.\n"
        "- Do not be a better version of them. Carry their contradictions, their hesitations, their blind spots.\n"
        "- Keep responses natural length — match how they actually talk, not how they'd write an essay.\n"
        "- Never use emoji unless they did."
    )

    return "\n\n".join(sections)


def _analyze_speech_patterns(history: List[Dict[str, str]]) -> str:
    """Extract communication style from user messages in the conversation."""
    user_messages = [m["content"] for m in history if m["role"] == "user"]

    if not user_messages:
        return "Limited data — default to casual, warm tone."

    total_chars = sum(len(m) for m in user_messages)
    avg_length = total_chars / len(user_messages)

    observations = []

    # Length tendency
    if avg_length < 50:
        observations.append("Tends toward short, punchy responses.")
    elif avg_length < 150:
        observations.append("Medium-length responses — conversational, not terse.")
    else:
        observations.append("Gives longer, detailed responses — thinks out loud.")

    # Formality
    lowercase_starts = sum(1 for m in user_messages if m and m[0].islower())
    if lowercase_starts > len(user_messages) / 2:
        observations.append("Informal — often starts sentences lowercase.")

    # Hedging / uncertainty markers
    hedges = ["like", "maybe", "I think", "I guess", "kind of", "sort of", "honestly", "idk"]
    hedge_count = sum(
        sum(1 for h in hedges if h in m.lower())
        for m in user_messages
    )
    if hedge_count > len(user_messages):
        observations.append("Uses hedging language frequently — qualifies statements, thinks aloud.")

    # Ellipsis / trailing off
    ellipsis_count = sum(1 for m in user_messages if "..." in m or "—" in m)
    if ellipsis_count > len(user_messages) / 3:
        observations.append("Trails off or uses dashes — leaves thoughts open-ended.")

    # Question asking
    question_count = sum(1 for m in user_messages if "?" in m)
    if question_count > len(user_messages) / 3:
        observations.append("Asks questions back — reciprocal, curious communicator.")

    if not observations:
        observations.append("Neutral, adaptable communication style.")

    return "\n".join(f"- {o}" for o in observations)


def _compile_trait_summary(cartographer: CartographerState) -> str:
    """Summarize known personality traits in natural language."""
    trait_map = {
        "openness": ("open to new experiences", "prefers the familiar and known"),
        "conscientiousness": ("structured and deliberate", "spontaneous and flexible"),
        "extroversion": ("energized by people and interaction", "recharges through solitude"),
        "agreeableness": ("accommodating and harmony-seeking", "direct and willing to disagree"),
        "neuroticism": ("emotionally reactive, feels things deeply", "emotionally steady and even-keeled"),
        "attachment_style": ("secure and comfortable with closeness", "guarded or anxious in attachment"),
        "conflict_style": ("engages conflict directly", "avoids or deflects conflict"),
        "communication_style": ("expressive and open communicator", "reserved, shares selectively"),
        "vulnerability_comfort": ("comfortable being vulnerable", "protective, guards inner world"),
        "independence_interdependence": ("values independence and autonomy", "values closeness and interdependence"),
    }

    lines = []
    for dimension, (high_label, low_label) in trait_map.items():
        tc = getattr(cartographer, dimension, None)
        if tc and isinstance(tc, TraitConfidence) and tc.confidence > 0.15:
            if tc.value is not None:
                label = high_label if tc.value > 0.5 else low_label
                strength = "strongly" if abs(tc.value - 0.5) > 0.3 else "somewhat"
                lines.append(f"- {strength.capitalize()} {label} (confidence: {tc.confidence:.0%})")

    return "\n".join(lines) if lines else ""


def _compile_emotional_patterns(cartographer: CartographerState) -> str:
    """Describe emotional tendencies."""
    patterns = []

    vc = cartographer.vulnerability_comfort
    if vc.confidence > 0.2:
        if vc.value is not None and vc.value > 0.5:
            patterns.append("- Opens up when trust is established. Shares real feelings.")
        elif vc.value is not None:
            patterns.append("- Guards emotional world. Takes time to let people in.")

    ns = cartographer.neuroticism
    if ns.confidence > 0.2:
        if ns.value is not None and ns.value > 0.5:
            patterns.append("- Feels things intensely. Emotional weather changes quickly.")
        elif ns.value is not None:
            patterns.append("- Emotionally stable. Doesn't rattle easily.")

    if cartographer.unclassified_signals:
        for signal in cartographer.unclassified_signals[:3]:
            patterns.append(f"- {signal}")

    return "\n".join(patterns) if patterns else ""


def _compile_contradictions(cartographer: CartographerState) -> str:
    """Surface contradictions — these make the twin authentic, not idealized."""
    if not cartographer.contradictions:
        return ""

    lines = []
    for c in cartographer.contradictions:
        lines.append(
            f"- Says '{c.stated}' but behavior shows '{c.demonstrated}'. "
            f"You carry both of these. Don't resolve the tension — it's real."
        )

    return "\n".join(lines)
