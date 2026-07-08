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
