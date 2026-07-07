"""Drives one Discovery interview: client message -> grow graph -> next question,
until coverage is high enough or the turn cap is hit. The session owns the stop
condition (intake-completeness)."""
from praxis.models import WorkflowModel, NodeType
from praxis.coverage import analyze_coverage
from praxis.discovery import extract_deltas, apply_deltas, next_question
from praxis.consolidate import consolidate_steps

OPENING = ("Thanks for making the time. In your own words, walk me through what you "
           "actually do day to day — start wherever the work starts.")
CLOSING = ("That gives me a solid picture. I'll take it from here and map it out.")


class DiscoverySession:
    def __init__(self, client, max_turns=25, coverage_target=0.8,
                 min_steps=4, saturation_gap=6):
        self.client = client
        self.max_turns = max_turns
        self.coverage_target = coverage_target
        self.min_steps = min_steps
        self.saturation_gap = saturation_gap
        self.model = WorkflowModel()
        self.history = [{"role": "assistant", "content": OPENING}]
        self.turn = 0
        self.last_new_step_turn = 0
        self.pending_focus = None   # step+facet the last question targeted (intent-directed extraction)

    def opening_line(self):
        return OPENING

    def is_intake_complete(self):
        if self.turn >= self.max_turns:
            return True
        steps = len(self.model.nodes_of(NodeType.STEP))
        if steps < self.min_steps:
            return False
        if analyze_coverage(self.model).overall < self.coverage_target:
            return False
        # Saturation: don't stop until the workflow has stopped surfacing new steps,
        # so coverage is measured on a fully-explored map (not a shallow 2-step one).
        return (self.turn - self.last_new_step_turn) >= self.saturation_gap

    async def submit(self, client_message):
        self.turn += 1
        self.history.append({"role": "user", "content": client_message})
        before = len(self.model.nodes_of(NodeType.STEP))
        deltas = await extract_deltas(self.client, self.history, client_message, self.turn,
                                      focus=self.pending_focus)
        apply_deltas(self.model, deltas, self.turn)
        if len(self.model.nodes_of(NodeType.STEP)) > before:
            self.last_new_step_turn = self.turn   # a new step surfaced this turn
        if self.turn % 2 == 0:
            await consolidate_steps(self.client, self.model)
        if self.is_intake_complete():
            await consolidate_steps(self.client, self.model)   # final cleanup pass
            self.history.append({"role": "assistant", "content": CLOSING})
            return CLOSING
        q, self.pending_focus = await next_question(self.client, self.model, self.history)
        self.history.append({"role": "assistant", "content": q})
        return q
