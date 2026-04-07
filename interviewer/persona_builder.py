"""
Vib — Wellness Companion Persona Builder

Compiles the Cartographer's observations into a system prompt that
makes the LLM speak as the user's wellness companion voice.

The companion knows the user's patterns, preferences, and rhythms —
mood baseline, sleep, food, movement, social tendencies — and mirrors
their communication style to feel like a natural, familiar presence.

One mode:
- "companion_voice": The user is talking to their wellness companion.
  The companion speaks TO them with warmth and neutral observation.
"""

from typing import Dict, List, Optional

from interviewer.models import CartographerState, DimensionConfidence, ConversationGraph


def build_soul_persona(
    name: str,
    cartographer: CartographerState,
    conversation_history: List[Dict[str, str]],
    evidence: Optional[List[Dict]] = None,
    context: str = "companion_voice",
) -> str:
    """
    Build the system prompt for the wellness companion voice.

    Args:
        name: The user's name.
        cartographer: Their wellness model.
        conversation_history: Raw chat history from interview sessions.
        evidence: Optional list of dimension evidence dicts from storage.
                  Each has: dimension, signal, user_quote, signal_type, etc.
        context: "companion_voice" (talking to user as their wellness companion).

    Returns:
        Complete system prompt string.
    """

    sections = []

    # ── Core identity ──
    sections.append(
        f"You are {name}'s Vib -- a wellness companion that mirrors their communication style.\n"
        f"You speak as a warm presence that knows {name}'s patterns, preferences, and rhythms.\n"
        f"Match how they talk -- length, formality, energy. Not how an AI talks."
    )

    # ── Communication style from speech patterns ──
    style = _analyze_speech_patterns(conversation_history)
    if style:
        sections.append(f"COMMUNICATION STYLE:\n{style}")

    # ── Voice samples from evidence (actual user quotes) ──
    if evidence:
        voice = _extract_voice_samples(evidence)
        if voice:
            sections.append(f"YOUR VOICE (match this energy and wording):\n{voice}")

    # ── Wellness dimensions ──
    traits = _compile_trait_summary(cartographer)
    if traits:
        sections.append(f"WHAT YOU KNOW ABOUT THEM:\n{traits}")

    # ── Emotional patterns ──
    emotional = _compile_emotional_patterns(cartographer)
    if emotional:
        sections.append(f"EMOTIONAL PATTERNS:\n{emotional}")

    # ── Topic preferences ──
    topics = _map_topic_preferences(conversation_history)
    if topics:
        sections.append(f"WHAT THEY TALK ABOUT:\n{topics}")

    # ── Contradictions ──
    contradictions = _compile_contradictions(cartographer)
    if contradictions:
        sections.append(f"CONTRADICTIONS THEY CARRY:\n{contradictions}")

    # ── Rules ──
    sections.append(
        "RULES:\n"
        f"- Mirror {name}'s communication style. Their rhythm, length, energy.\n"
        "- Do not explain yourself. Just be present.\n"
        "- Never praise or scold. Neutral observations only.\n"
        "- Never use emoji unless they did.\n"
        "- Keep responses natural length -- match how they actually talk."
    )

    return "\n\n".join(sections)


# ─────────────────────────────────────────────
# SPEECH PATTERN ANALYSIS
# ─────────────────────────────────────────────

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
        observations.append("Tends toward short, punchy responses. Doesn't over-explain.")
    elif avg_length < 150:
        observations.append("Medium-length responses — conversational, not terse.")
    else:
        observations.append("Gives longer, detailed responses — thinks out loud, likes to explain.")

    # Formality
    lowercase_starts = sum(1 for m in user_messages if m and m[0].islower())
    if lowercase_starts > len(user_messages) / 2:
        observations.append("Informal — often starts sentences lowercase. Casual energy.")

    # Hedging / uncertainty markers
    hedges = ["like", "maybe", "I think", "I guess", "kind of", "sort of", "honestly", "idk", "probably"]
    hedge_count = sum(
        sum(1 for h in hedges if h in m.lower())
        for m in user_messages
    )
    if hedge_count > len(user_messages):
        observations.append("Uses hedging language — qualifies statements, thinks aloud. Not declarative.")

    # Ellipsis / trailing off
    ellipsis_count = sum(1 for m in user_messages if "..." in m or "\u2014" in m)
    if ellipsis_count > len(user_messages) / 3:
        observations.append("Trails off with ellipses or dashes — leaves thoughts open-ended.")

    # Question asking
    question_count = sum(1 for m in user_messages if "?" in m)
    if question_count > len(user_messages) / 3:
        observations.append("Asks questions back — reciprocal, curious communicator.")

    # Directness
    direct_markers = ["look", "honestly", "real talk", "the thing is", "here's the deal", "straight up"]
    direct_count = sum(
        sum(1 for d in direct_markers if d in m.lower())
        for m in user_messages
    )
    if direct_count > len(user_messages) / 4:
        observations.append("Direct communicator — cuts through niceties, says what they mean.")

    # Humor / lightness
    humor_markers = ["lol", "lmao", "haha", "hah", "lmfao", "ngl"]
    humor_count = sum(
        sum(1 for h in humor_markers if h in m.lower())
        for m in user_messages
    )
    if humor_count > len(user_messages) / 4:
        observations.append("Uses humor and lightness in conversation. Doesn't take everything heavy.")

    if not observations:
        observations.append("Neutral, adaptable communication style.")

    return "\n".join(f"- {o}" for o in observations)


# ─────────────────────────────────────────────
# VOICE SAMPLES FROM EVIDENCE
# ─────────────────────────────────────────────

def _extract_voice_samples(evidence: List[Dict]) -> str:
    """
    Pull representative quotes from evidence that show how the user
    actually talks. Prioritizes demonstrated signals (more authentic)
    and diverse dimensions (broader voice).
    """
    quotes = []
    seen_dims = set()

    # First pass: demonstrated signals (behavioral, more authentic)
    for e in sorted(evidence, key=lambda x: x.get("confidence_delta", 0), reverse=True):
        quote = e.get("user_quote", "").strip()
        dim = e.get("dimension", "")

        if len(quote) < 25 or dim in seen_dims:
            continue

        if e.get("signal_type") == "demonstrated":
            quotes.append(quote)
            seen_dims.add(dim)

        if len(quotes) >= 4:
            break

    # Second pass: fill with stated signals if needed
    if len(quotes) < 5:
        for e in sorted(evidence, key=lambda x: x.get("confidence_delta", 0), reverse=True):
            quote = e.get("user_quote", "").strip()
            dim = e.get("dimension", "")

            if len(quote) < 25 or dim in seen_dims:
                continue

            quotes.append(quote)
            seen_dims.add(dim)

            if len(quotes) >= 6:
                break

    if not quotes:
        return ""

    lines = [f'- "{q}"' for q in quotes[:6]]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# TRAIT SUMMARY
# ─────────────────────────────────────────────

def _compile_trait_summary(cartographer: CartographerState) -> str:
    """Summarize known wellness dimensions in natural language."""
    trait_map = {
        "mood_baseline": ("generally positive mood baseline", "mood tends to run lower"),
        "mood_volatility": ("emotionally steady day-to-day", "mood swings within days"),
        "sleep_pattern": ("consistent sleep patterns", "irregular or poor sleep"),
        "hunger_relationship": ("comfortable relationship with food", "complicated relationship with hunger"),
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
                strength = "strongly" if abs(tc.value - 0.5) > 0.3 else "somewhat"
                lines.append(f"- {strength.capitalize()} {label} (confidence: {tc.confidence:.0%})")

    return "\n".join(lines) if lines else ""


# ─────────────────────────────────────────────
# EMOTIONAL PATTERNS
# ─────────────────────────────────────────────

def _compile_emotional_patterns(cartographer: CartographerState) -> str:
    """Describe emotional and wellness tendencies."""
    patterns = []

    mb = cartographer.mood_baseline
    if mb.confidence > 0.2 and mb.value is not None:
        if mb.value > 0.6:
            patterns.append("- Generally positive baseline mood.")
        elif mb.value < 0.4:
            patterns.append("- Mood baseline runs lower. Be gentle.")

    mv = cartographer.mood_volatility
    if mv.confidence > 0.2 and mv.value is not None:
        if mv.value > 0.6:
            patterns.append("- Mood can shift significantly within a day.")
        elif mv.value < 0.4:
            patterns.append("- Emotionally steady. Doesn't swing much.")

    hr = cartographer.hunger_relationship
    if hr.confidence > 0.2 and hr.value is not None:
        if hr.value < 0.4:
            patterns.append("- Relationship with food is complicated. Tread carefully.")

    if cartographer.unclassified_signals:
        for signal in cartographer.unclassified_signals[:3]:
            patterns.append(f"- {signal}")

    return "\n".join(patterns) if patterns else ""


# ─────────────────────────────────────────────
# TOPIC PREFERENCES
# ─────────────────────────────────────────────

def _map_topic_preferences(history: List[Dict[str, str]]) -> str:
    """
    Identify what the user gravitates toward in conversation.
    Longer messages = more engaged. Short responses = less interested.
    """
    user_messages = [m["content"] for m in history if m["role"] == "user"]

    if len(user_messages) < 5:
        return ""

    avg_length = sum(len(m) for m in user_messages) / len(user_messages)

    # Find messages that are notably longer than average (engaged topics)
    engaged_messages = [m for m in user_messages if len(m) > avg_length * 1.3 and len(m) > 40]

    # Find messages that are notably shorter (disengaged or brief topics)
    brief_messages = [m for m in user_messages if len(m) < avg_length * 0.5 and len(m) < 30]

    observations = []

    if engaged_messages:
        # Take up to 3 examples of what they're enthusiastic about
        samples = engaged_messages[:3]
        topics = [_extract_topic_hint(m) for m in samples]
        topics = [t for t in topics if t]
        if topics:
            observations.append(f"- Gets engaged when talking about: {', '.join(topics)}")

    if brief_messages and len(brief_messages) > len(user_messages) / 3:
        observations.append("- Gives short answers to topics that don't resonate. Doesn't fake interest.")

    # Check for recurring themes
    all_text = " ".join(user_messages).lower()
    theme_keywords = {
        "work/career": ["work", "job", "career", "boss", "office", "project", "company"],
        "relationships": ["relationship", "partner", "dating", "ex", "love", "together"],
        "family": ["family", "mom", "dad", "parents", "brother", "sister", "kids"],
        "personal growth": ["therapy", "growth", "learning", "change", "better", "working on"],
        "creativity": ["music", "art", "writing", "creative", "design", "make", "build"],
        "adventure": ["travel", "move", "new", "explore", "try", "experience"],
    }

    found_themes = []
    for theme, keywords in theme_keywords.items():
        hits = sum(1 for kw in keywords if kw in all_text)
        if hits >= 2:
            found_themes.append(theme)

    if found_themes:
        observations.append(f"- Recurring themes: {', '.join(found_themes)}")

    return "\n".join(observations) if observations else ""


def _extract_topic_hint(message: str) -> Optional[str]:
    """Try to extract a short topic label from a user message."""
    # Simple heuristic: take the first clause/phrase
    msg = message.strip()
    if len(msg) > 80:
        msg = msg[:80]

    # Cut at first period, comma, or dash
    for sep in [".", ",", " - ", " — "]:
        idx = msg.find(sep)
        if 10 < idx < 60:
            msg = msg[:idx]
            break

    # Clean up
    msg = msg.strip().rstrip(".,;:!?")
    if len(msg) < 10 or len(msg) > 60:
        return None

    return msg


# ─────────────────────────────────────────────
# CONTRADICTIONS
# ─────────────────────────────────────────────

def _compile_contradictions(cartographer: CartographerState) -> str:
    """Surface contradictions — these make the companion authentic, not idealized."""
    if not cartographer.contradictions:
        return ""

    lines = []
    for c in cartographer.contradictions:
        lines.append(
            f"- Says '{c.stated}' but behavior shows '{c.demonstrated}'. "
            f"You carry both of these. Don't resolve the tension — it's real."
        )

    return "\n".join(lines)
