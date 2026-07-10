"""The shared engagement blackboard + recorded log. Every agent reads from and writes to
one EngagementState (so any agent can use any other agent's output), and every action and
hand-off between agents is recorded on the log — including non-linear bounces (Skeptic ->
Architect redo) and consults (one agent asking another's point of view)."""
from dataclasses import dataclass, field, asdict


@dataclass
class Fixture:
    """A REAL sample of the business's own data — a work order the owner read out, the OCR of an
    actual ticket photo, a real part number. This is the ground truth SP2's Airlock Verifier
    tests generated automation against; without it, SP2 would verify invented logic against
    invented data. Captured from ingested materials and concrete interview examples."""
    sample: str                 # the actual data/content
    source: str                 # where it came from (a filename, or "interview")
    step_label: str = ""        # the workflow step it exemplifies, if known


@dataclass
class Event:
    seq: int
    agent: str            # who acted: analyst / architect / business_case / skeptic / principal
    action: str           # what they did
    detail: str = ""      # human-readable summary
    consumed_from: str = ""   # whose output they used (the hand-off)
    count: int = 0        # items produced/affected


@dataclass
class EngagementState:
    """The blackboard: the map + everything the firm produces, plus the recorded log."""
    model_dict: dict = field(default_factory=dict)
    transcript: list = field(default_factory=list)      # the Discovery interview
    opportunities: list = field(default_factory=list)   # Analyst
    interventions: list = field(default_factory=list)   # Architect
    assessments: list = field(default_factory=list)     # Business-case
    verdicts: list = field(default_factory=list)        # Skeptic
    deliverable: dict = field(default_factory=dict)     # Principal
    fixtures: list = field(default_factory=list)        # real I/O samples (ground truth for SP2)
    log: list = field(default_factory=list)             # list[Event]

    def record(self, agent, action, detail="", consumed_from="", count=0):
        self.log.append(Event(len(self.log) + 1, agent, action, detail, consumed_from, count))

    def to_dict(self):
        return {
            "map": self.model_dict,
            "transcript": self.transcript,
            "opportunities": [asdict(o) for o in self.opportunities],
            "interventions": [asdict(i) for i in self.interventions],
            "assessments": [asdict(a) for a in self.assessments],
            "verdicts": [asdict(v) for v in self.verdicts],
            "deliverable": self.deliverable,
            "fixtures": [asdict(f) for f in self.fixtures],
            "log": [asdict(e) for e in self.log],
        }
