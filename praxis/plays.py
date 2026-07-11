"""Content-free interview 'plays'. Each play is a rule about interview DYNAMICS
(trigger -> question directive), never about business domain (Ocean Principle).
This registry is the substrate a future learning loop will extend."""
from dataclasses import dataclass
from typing import Callable
from praxis.models import NodeType, EdgeType
from praxis.coverage import analyze_coverage, step_facets, is_satisfied
from praxis.discovery_signals import is_vague

_FACET_Q = {
    "actor": "who does it",
    "tool": "what tool they use",
    "input": "what they start with",
    "output": "what it produces",
}


@dataclass
class InterviewState:
    model: object
    last_answer: str = ""
    # Foci already probed this interview ("step_label|facet"). Once asked, we move on even if
    # the map facet is still empty — re-asking the same facet is the discovery loop failure.
    probed_foci: set = None

    def __post_init__(self):
        if self.probed_foci is None:
            self.probed_foci = set()

    @property
    def coverage(self):
        return analyze_coverage(self.model)

    def focus_key(self, step_label, facet):
        return f"{(step_label or '').strip().lower()}|{(facet or '').strip().lower()}"


@dataclass
class Play:
    id: str
    kind: str
    priority: int
    matches: Callable
    focus: Callable


def _steps(state):
    return state.model.nodes_of(NodeType.STEP)


def _nonfriction_gap(state):
    """Return (step_node, missing_facets) for the UNSATISFIED step closest to done
    (fewest missing required facets), so we finish steps rather than spreading thin.
    A step is satisfied at actor + tool + (input OR output); missing facets beyond that
    are not chased here. None if every step is already satisfied.

    Skips foci already probed this interview — once we asked about a step's tool/actor,
    we do not re-ask even if extraction never attached the edge. That is the fix for the
    discovery loop that re-asked 'do you re-type into the contract?' four times."""
    m = state.model
    best = None
    for s in _steps(state):
        f = step_facets(m, s.id)
        if is_satisfied(f):
            continue
        missing = []
        if not f["actor"] and state.focus_key(s.label, "actor") not in state.probed_foci:
            missing.append("actor")
        if not (f["tool"] or f["input"] or f["output"]):
            # Need a concrete anchor. Probe tool → input → output once each; after all are
            # probed without a hit, stop chasing this step (don't re-ask forever).
            for cand in ("tool", "input", "output"):
                if state.focus_key(s.label, cand) not in state.probed_foci:
                    missing.append(cand)
                    break
        if not missing:
            continue
        if best is None or len(missing) < len(best[1]):
            best = (s, missing)
    return best


def _satisfied_step_without_friction(state):
    m = state.model
    for s in _steps(state):
        f = step_facets(m, s.id)
        if is_satisfied(f) and not f["friction"]:
            return s
    return None


def _sequence_count(state):
    return sum(1 for e in state.model.edges.values() if e.type == EdgeType.SEQUENCE)


REGISTRY = [
    Play("establish_first_step", "question", 90,
         matches=lambda st: len(_steps(st)) == 0,
         focus=lambda st: ("No step is mapped yet. Ask them to name, in a few words, "
                           "the very first thing that happens when the work starts.")),
    Play("probe_after_vague", "question", 60,
         matches=lambda st: is_vague(st.last_answer) and len(_steps(st)) > 0,
         focus=lambda st: ("Their last answer was vague. Ask them to walk you through the "
                           "most recent actual time this happened, concretely, start to finish.")),
    # BREADTH-FIRST: trace the whole spine to the end BEFORE drilling any step's details. This
    # outranks facet-completion (75 > 70) so the interview walks the entire job — intake, core
    # work, delivery, billing — instead of rat-holing on the first few steps and never reaching
    # the middle (the failure that lost a photographer's whole editing/delivery half). Once the
    # spine is fully chained, this stops matching and facet-completion fills in the details.
    Play("trace_sequence", "question", 75,
         matches=lambda st: len(_steps(st)) >= 1 and _sequence_count(st) < len(_steps(st)) - 1,
         focus=lambda st: ("Ask what happens immediately after the most recently "
                           "described step — keep moving FORWARD through their process.")),
    Play("complete_step_facets", "question", 70,
         matches=lambda st: _nonfriction_gap(st) is not None,
         focus=lambda st: (lambda g: f"For the step '{g[0].label}', find out: "
                           + ", ".join(_FACET_Q[f] for f in g[1])
                           + ". Ask one concrete question about it.")(_nonfriction_gap(st))),
    # Below trace_sequence and facets on purpose: map the WHOLE workflow first, then probe pain,
    # so the interview doesn't fixate on one vivid friction and lose breadth. Synthesis mines
    # pain from the full transcript regardless.
    Play("surface_friction", "question", 30,
         matches=lambda st: _satisfied_step_without_friction(st) is not None,
         focus=lambda st: (f"For the step '{_satisfied_step_without_friction(st).label}', ask "
                           "one quick question about what's most annoying or error-prone there, "
                           "then move on — don't dwell.")),
    Play("fallback", "question", 0,
         matches=lambda st: True,
         focus=lambda st: ("Ask about a part of their work you HAVEN'T covered yet — what "
                           "happens before this starts, after it ends, or alongside it that "
                           "you haven't discussed. Map the whole job, not just this slice.")),
]


def select_play(state: InterviewState) -> Play:
    candidates = [p for p in REGISTRY if p.matches(state)]
    return max(candidates, key=lambda p: p.priority)


def focus_target(state: InterviewState):
    """The structured intent of the selected play: which step + facet the next question
    is trying to complete, so the extractor can attach the client's answer to that step.
    None when the selected play isn't targeting a specific step's facet. Uses the same
    state (including probed_foci) so intent matches the play that was selected."""
    play = select_play(state)
    if play.id == "complete_step_facets":
        g = _nonfriction_gap(state)
        if g:
            return {"step_label": g[0].label, "facet": (g[1][0] if g[1] else "actor")}
    return None
