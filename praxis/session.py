"""Drives one Discovery interview: client message -> grow graph -> next question,
until coverage is high enough or the turn cap is hit. The session owns the stop
condition (intake-completeness)."""
from praxis.models import WorkflowModel, NodeType
from praxis.coverage import analyze_coverage
from praxis.discovery import extract_deltas, apply_deltas, next_question

OPENING = ("Thanks for making the time. In your own words, walk me through what you "
           "actually do day to day — start wherever the work starts.")
CLOSING = ("That gives me a solid picture. I'll take it from here and map it out.")


class DiscoverySession:
    def __init__(self, client, max_turns=25, coverage_target=0.8):
        self.client = client
        self.max_turns = max_turns
        self.coverage_target = coverage_target
        self.model = WorkflowModel()
        self.history = [{"role": "assistant", "content": OPENING}]
        self.turn = 0

    def opening_line(self):
        return OPENING

    def is_intake_complete(self):
        if self.turn >= self.max_turns:
            return True
        rep = analyze_coverage(self.model)
        return len(self.model.nodes_of(NodeType.STEP)) >= 2 and rep.overall >= self.coverage_target

    async def submit(self, client_message):
        self.turn += 1
        self.history.append({"role": "user", "content": client_message})
        deltas = await extract_deltas(self.client, self.history, client_message, self.turn)
        apply_deltas(self.model, deltas, self.turn)
        if self.is_intake_complete():
            self.history.append({"role": "assistant", "content": CLOSING})
            return CLOSING
        q = await next_question(self.client, self.model, self.history)
        self.history.append({"role": "assistant", "content": q})
        return q
