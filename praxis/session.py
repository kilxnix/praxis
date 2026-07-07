"""Drives one Discovery interview: client message -> grow graph -> next question,
until coverage is high enough or the turn cap is hit. The session owns the stop
condition (intake-completeness)."""
from praxis.models import WorkflowModel, NodeType
from praxis.coverage import analyze_coverage
from praxis.discovery import extract_deltas, apply_deltas, next_question
from praxis.consolidate import consolidate_steps
from praxis.completeness import assess_completeness

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
        self._closed = False
        self.completeness_focus = None       # a missing phase to chase before we conclude
        self.completeness_extensions = 0
        self.max_completeness_extensions = 3  # bound the "keep going" so it can't loop forever

    def opening_line(self):
        return OPENING

    def is_intake_complete(self):
        # Authoritative stop for the interview loop: the turn cap, or we deliberately closed.
        return self.turn >= self.max_turns or self._closed

    def _saturated(self):
        # Candidate stop: enough well-specified steps AND no new step for a while. This is only
        # a CANDIDATE now — the completeness gate decides whether we actually stop.
        if len(self.model.nodes_of(NodeType.STEP)) < self.min_steps:
            return False
        if analyze_coverage(self.model).overall < self.coverage_target:
            return False
        return (self.turn - self.last_new_step_turn) >= self.saturation_gap

    async def _close(self):
        await consolidate_steps(self.client, self.model)   # final cleanup pass
        self._closed = True
        self.history.append({"role": "assistant", "content": CLOSING})
        return CLOSING

    async def submit(self, client_message):
        if self._closed:
            return CLOSING
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

        if self.turn >= self.max_turns:
            return await self._close()

        if self._saturated():
            if self.completeness_extensions >= self.max_completeness_extensions:
                return await self._close()          # gave it enough chances; conclude
            check = await assess_completeness(self.client, self.model)
            if check.get("complete"):
                return await self._close()
            # Not the whole job yet — steer the next question at the missing phase and keep going.
            self.completeness_focus = (
                "We haven't mapped the whole job yet — " + (check.get("missing") or "")
                + ". Ask them about that part of their work.")
            self.completeness_extensions += 1
            self.last_new_step_turn = self.turn     # reset saturation so it explores further

        override = self.completeness_focus
        self.completeness_focus = None
        q, self.pending_focus = await next_question(self.client, self.model, self.history,
                                                    focus_override=override)
        self.history.append({"role": "assistant", "content": q})
        return q
