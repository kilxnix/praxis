"""Deterministic, content-free signals for Discovery v2. No LLM, no network.
Reads conversational FORM (length, hedges) and normalizes labels —
never classifies business content (Ocean Principle)."""
import re

_ARTICLES = {"the", "a", "an", "my", "our", "your", "their", "his", "her", "its"}
_HEDGE = {"hoping", "hope", "maybe", "because", "wish", "guess", "guessing",
          "probably", "kinda", "sorta", "somehow", "whatever"}

# Leading verbs that signal a NON-activity: a wait, a pause, a passive state, or a mistake —
# not a real business step that moves the work forward. Breadth-first tracing surfaces a lot of
# these ("wait by notebook", "hang up", "mishear a number"); they inflate the map and everything
# downstream. Content-free FORM signal (is this an action or a non-action), not domain judgment.
_NON_ACTIVITY_LEADS = {
    "wait", "waiting", "pause", "pausing", "hang", "sit", "sitting", "stand", "standing",
    "think", "thinking", "remember", "remembering", "recall", "forget", "forgetting",
    "mishear", "misread", "hope", "worry", "worrying", "guess", "rest", "resting", "idle",
}


def canonical_label(raw: str) -> str:
    s = (raw or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    toks = [t for t in s.split() if t]
    while toks and toks[0] in _ARTICLES:
        toks.pop(0)
    return " ".join(toks)


def is_valid_step_label(raw: str) -> bool:
    s = (raw or "").strip()
    if not s:
        return False
    if "?" in s:
        return False
    words = s.split()
    if len(words) > 5:
        return False
    low = {w.lower().strip(".,!?") for w in words}
    if low & _HEDGE:
        return False
    # Reject non-activities (waits, pauses, passive states, mistakes) by their leading verb —
    # these aren't steps that move the work forward.
    first = words[0].lower().strip(".,!?")
    if first in _NON_ACTIVITY_LEADS:
        return False
    return True


def is_vague(answer: str) -> bool:
    a = (answer or "").strip()
    if not a:
        return True
    words = a.split()
    if len(words) < 5:
        return True
    low = {w.lower().strip(".,!?") for w in words}
    return bool(low & _HEDGE)
