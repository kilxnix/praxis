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

    @property
    def coverage(self):
        return analyze_coverage(self.model)


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
    are not chased here. None if every step is already satisfied."""
    m = state.model
    best = None
    for s in _steps(state):
        f = step_facets(m, s.id)
        if is_satisfied(f):
            continue
        missing = []
        if not f["actor"]:
            missing.append("actor")
        if not (f["tool"] or f["input"] or f["output"]):
            missing.append("output")
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
    Play("complete_step_facets", "question", 70,
         matches=lambda st: _nonfriction_gap(st) is not None,
         focus=lambda st: (lambda g: f"For the step '{g[0].label}', find out: "
                           + ", ".join(_FACET_Q[f] for f in g[1])
                           + ". Ask one concrete question about it.")(_nonfriction_gap(st))),
    Play("probe_after_vague", "question", 60,
         matches=lambda st: is_vague(st.last_answer) and len(_steps(st)) > 0,
         focus=lambda st: ("Their last answer was vague. Ask them to walk you through the "
                           "most recent actual time this happened, concretely, start to finish.")),
    Play("trace_sequence", "question", 40,
         matches=lambda st: len(_steps(st)) >= 1 and _sequence_count(st) < len(_steps(st)) - 1,
         focus=lambda st: ("Ask what happens immediately after the most recently "
                           "described step.")),
    Play("surface_friction", "question", 20,
         matches=lambda st: _satisfied_step_without_friction(st) is not None,
         focus=lambda st: (f"For the step '{_satisfied_step_without_friction(st).label}', "
                           "ask what usually goes wrong or slows them down there.")),
    Play("fallback", "question", 0,
         matches=lambda st: True,
         focus=lambda st: ("Ask what happens next in the process, or which part of this "
                           "work is the most annoying or error-prone.")),
]


def select_play(state: InterviewState) -> Play:
    candidates = [p for p in REGISTRY if p.matches(state)]
    return max(candidates, key=lambda p: p.priority)
