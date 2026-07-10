"""Owned judgment — NOT the LLM's opinion.

The language model extracts and phrases; it does NOT get to decide whether an opportunity is
worth acting on. That judgment is ours, and here it is MEASURED from the owner's own recorded
words, deterministically:

- is the anchor REAL? does the opportunity's evidence actually overlap what the owner said, or
  did the model invent it to justify a capability it wanted to apply? -> unsubstantiated = weak.
- does it RECUR? did the owner return to this step across multiple turns, or use their own
  frequency / duration language ("every night", "twenty minutes", "constantly")? -> recurring;
  a single passing mention with none of that -> one_off.

The thresholds here are the knobs the firm's minds learn to tune over engagements. The model
never votes on grounding — we count it.
"""
import re
from praxis.models import NodeType

# The owner expressing recurrence / cost in THEIR OWN words. Content-free FORM signals (how often
# / how long), never business-domain classification — consistent with the Ocean Principle.
_FREQUENCY_MARKERS = (
    "every", "everytime", "every time", "each time", "always", "constantly", "constant",
    "daily", "nightly", "every day", "every night", "all day", "all night", "all the time",
    "repeatedly", "over and over", "again and again", "keep", "keeps", "keeping", "whole",
    "entire", "hours", "minutes", "twenty minutes", "half an hour", "all morning", "all night",
    "never stops", "again",
)

_TOKEN = re.compile(r"[a-z0-9]+")

# Burden signals in the owner's OWN words — how much VOLUME or TIME a step costs them. This is
# how we decide which work matters most WITHOUT asking the model: a step where they said
# "thousands of photos" or "hours every night" outranks one they mentioned in passing. The
# clerical-drudgery bias (flag admin, ignore the heavy core work) is exactly what this corrects.
_QUANTITY = {"thousands", "thousand", "hundreds", "hundred", "dozens", "dozen", "many", "tons",
             "loads", "stacks", "stack", "pile", "piles", "reams", "countless", "numerous",
             "endless", "stack", "batches", "batch"}
_DURATION = {"hours", "hour", "forever", "ages", "all", "whole", "entire"}
_DURATION_PHRASES = ("all day", "all night", "all morning", "all evening", "half an hour",
                     "an hour", "twenty minutes", "thirty minutes", "hours every")


def _tokens(text):
    return set(_TOKEN.findall((text or "").lower()))


def _step_evidence(model, step_label):
    """Every quote the owner gave that anchors this step, with the turns they said them on."""
    for n in model.nodes_of(NodeType.STEP):
        if n.label == step_label:
            return [(ev.quote, ev.turn) for ev in n.evidence]
    return []


def _all_owner_words(model):
    """Every word the owner actually said, as captured verbatim across the whole map."""
    words = set()
    for n in model.nodes.values():
        for ev in n.evidence:
            words |= _tokens(ev.quote)
    return words


def substantiation(opp_evidence, owner_words):
    """Fraction of the opportunity's evidence words that actually appear in the owner's words.
    Low overlap => the anchor was invented to justify a capability, not drawn from what they said."""
    ev = _tokens(opp_evidence)
    if not ev:
        return 0.0
    return len(ev & owner_words) / len(ev)


def has_frequency_language(quotes):
    text = " ".join(quotes).lower()
    return any(m in text for m in _FREQUENCY_MARKERS)


def _turn_context(transcript, turns):
    """The FULL owner text of the conversation turns a step's evidence came from. The extracted
    step label ('create digital drafts') is terse, but the owner's actual answer on that turn
    ('3-4 directions per project, which takes many hours') carries the volume/time signal — so a
    step's real burden lives in the turn, not the terse label. Owned: still the owner's own words,
    just a wider window."""
    if not transcript:
        return ""
    # transcript is [{role, content}]; discovery numbers turns from 1 as user messages arrive.
    user_msgs = [m.get("content", "") for m in transcript if m.get("role") == "user"]
    parts = []
    for t in turns:
        if 1 <= t <= len(user_msgs):
            parts.append(user_msgs[t - 1])
    return " ".join(parts)


def measure_burden(step_label, model, transcript=None):
    """Score how much VOLUME/TIME a step costs the owner, measured from their own words — 0 (a
    passing mention) up. Quantity words ("thousands"), duration ("hours", "twenty minutes"),
    numbers, frequency, and returning to the step across turns all raise it. Owned, not asked.
    When the transcript is supplied, also reads the FULL owner answer on the step's turns, so a
    core step whose volume signal didn't attach to its terse label ('create digital drafts' <-
    '3-4 directions, many hours') still measures its true burden."""
    step_ev = _step_evidence(model, step_label)
    turns = {t for _, t in step_ev}
    quotes = [q for q, _ in step_ev]
    text = (" ".join(quotes) + " " + _turn_context(transcript, turns)).lower()
    toks = _tokens(text)
    score = 0
    if toks & _QUANTITY:
        score += 2
    if (toks & _DURATION) or any(p in text for p in _DURATION_PHRASES):
        score += 2
    if re.search(r"\b\d{2,}\b", text):          # a written-out count like "20 minutes", "300"
        score += 1
    if any(m in text for m in _FREQUENCY_MARKERS):
        score += 1
    if len(turns) >= 2:
        score += 1
    return score


def burden_severity(score):
    """Map a measured burden score to the severity tier the deliverable ranks by."""
    if score >= 2:
        return "high"
    if score == 1:
        return "medium"
    return "low"


def measure_grounding(opportunity, model, min_substantiation=0.5):
    """Return 'recurring' | 'one_off' | 'weak', MEASURED from the owner's words — not asked.
    - weak:      the anchor isn't substantiated by anything the owner actually said (invented to
                 justify a capability).
    - recurring: substantiated AND (the owner returned to this step across >=2 turns OR used
                 frequency/duration language in their own words).
    - one_off:   substantiated, but a single mention with no frequency language.
    """
    if substantiation(opportunity.evidence, _all_owner_words(model)) < min_substantiation:
        return "weak"

    step_ev = _step_evidence(model, opportunity.step_label)
    turns = {t for _, t in step_ev}
    quotes = [q for q, _ in step_ev] + [opportunity.evidence]
    if len(turns) >= 2 or has_frequency_language(quotes):
        return "recurring"
    return "one_off"
