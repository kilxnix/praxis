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
    # micro-checks of a prior step ("double-check phone after hanging up") — HOW, not a step
    "double-check", "doublecheck", "recheck", "re-check",
    # meta umbrellas that name a whole job, not one activity ("manage existing pipeline")
    "manage", "focus",
    # third-party inbound events phrased as the vendor's verb ("delivers images") — not the
    # owner's work. Owner-side receive/accept stays allowed via other verbs.
    "delivers", "arrives", "lands",
}

# Phrase-level micro-motions / non-steps (FORM, not domain). Substring match on the label.
_MICRO_PHRASES = (
    "hanging up", "after hanging", "double-check", "double check",
    "cross out", "right after hanging", "while still fresh",
)

# Outcome umbrellas: "get properties listed" is the result of many real steps, not one step.
_UMBRELLA_MARKERS = (
    "pipeline",           # manage / work the pipeline
    "get listed", "properties listed", "getting listed",
)


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
    # "double check …" as two tokens
    if first == "double" and len(words) > 1 and words[1].lower().startswith("check"):
        return False
    joined = " ".join(w.lower() for w in words)
    if any(p in joined for p in _MICRO_PHRASES):
        return False
    if any(u in joined for u in _UMBRELLA_MARKERS):
        return False
    # "get X listed" umbrella outcome
    if first == "get" and "listed" in joined:
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
