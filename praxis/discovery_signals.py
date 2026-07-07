"""Deterministic, content-free signals for Discovery v2. No LLM, no network.
Reads conversational FORM (length, hedges, novelty) and normalizes labels —
never classifies business content (Ocean Principle)."""
import re

_ARTICLES = {"the", "a", "an", "my", "our", "your", "their", "his", "her", "its"}
_HEDGE = {"hoping", "hope", "maybe", "because", "wish", "guess", "guessing",
          "probably", "kinda", "sorta", "somehow", "whatever"}


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
