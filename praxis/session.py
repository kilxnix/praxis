"""Drives one Discovery interview: client message -> grow graph -> next question,
until coverage is high enough or the turn cap is hit. The session owns the stop
condition (intake-completeness)."""
import asyncio
from praxis.models import WorkflowModel, NodeType
from praxis.coverage import analyze_coverage
from praxis.discovery import extract_deltas, apply_deltas, next_question
from praxis.consolidate import consolidate_steps
from praxis.arc import REQUIRED, next_unasked_probe, arc_traversed
from praxis.analyst import serialize_map
from praxis.firm_agent import assemble_firm

OPENING = ("Thanks for making the time. In your own words, walk me through what you "
           "actually do day to day — start wherever the work starts.")
CLOSING = ("That gives me a solid picture. I'll take it from here and map it out.")


class DiscoverySession:
    def __init__(self, client, max_turns=25, coverage_target=0.8,
                 min_steps=4, saturation_gap=6, live_firm=True, firm=None):
        self.client = client
        self.max_turns = max_turns
        self.coverage_target = coverage_target
        self.min_steps = min_steps
        self.saturation_gap = saturation_gap
        # The firm sits in on the interview: each member watches the live discovery and builds
        # their own growing understanding of THIS business. None until first use so a cheap
        # run (live_firm=False) skips it entirely.
        self.live_firm = live_firm
        self.firm = firm if firm is not None else (assemble_firm(client) if live_firm else None)
        self.model = WorkflowModel()
        self.history = [{"role": "assistant", "content": OPENING}]
        self.turn = 0
        self.last_new_step_turn = 0
        self.pending_focus = None   # step+facet the last question targeted (intent-directed extraction)
        self._closed = False
        self.arc_asked = set()      # which required terminal probes we've asked (owned completeness)

    def opening_line(self):
        return OPENING

    def is_intake_complete(self):
        # Authoritative stop for the interview loop: the turn cap, or we deliberately closed.
        return self.turn >= self.max_turns or self._closed

    def _saturated(self):
        # Candidate stop: enough well-specified steps AND no new step for a while. This is only
        # a CANDIDATE — the interview may not actually conclude until the arc is traversed.
        if len(self.model.nodes_of(NodeType.STEP)) < self.min_steps:
            return False
        if analyze_coverage(self.model).overall < self.coverage_target:
            return False
        return (self.turn - self.last_new_step_turn) >= self.saturation_gap

    def _must_force_arc(self):
        # Force the terminal probes when the front is saturated OR the turn budget is running low,
        # and the arc hasn't been walked to its end yet. This is what stops the interview quitting
        # after the intake with the delivery/billing half of the job unmapped.
        approaching_cap = (self.max_turns - self.turn) <= len(REQUIRED) + 1
        return (self._saturated() or approaching_cap) and not arc_traversed(self.arc_asked)

    async def _firm_observe(self, last_question, answer):
        """Every firm member watches the latest exchange and updates what THEY understand about
        this business. Concurrent, so it costs one round-trip of latency, not five. Returns the
        number of new beliefs formed across the firm (for logging/visibility)."""
        if not self.firm:
            return 0
        exchange = f"Interviewer: {last_question}\nOwner: {answer}"
        map_text = serialize_map(self.model)
        added = await asyncio.gather(*[
            agent.observe(exchange, map_text, self.turn) for agent in self.firm.values()])
        return sum(added)

    async def _close(self):
        await consolidate_steps(self.client, self.model)   # final cleanup pass
        self._closed = True
        self.history.append({"role": "assistant", "content": CLOSING})
        return CLOSING

    async def submit(self, client_message):
        if self._closed:
            return CLOSING
        self.turn += 1
        last_question = self.history[-1]["content"] if self.history else OPENING
        self.history.append({"role": "user", "content": client_message})
        before = len(self.model.nodes_of(NodeType.STEP))
        deltas = await extract_deltas(self.client, self.history, client_message, self.turn,
                                      focus=self.pending_focus)
        apply_deltas(self.model, deltas, self.turn)
        if len(self.model.nodes_of(NodeType.STEP)) > before:
            self.last_new_step_turn = self.turn   # a new step surfaced this turn
        if self.turn % 2 == 0:
            await consolidate_steps(self.client, self.model)

        # The firm sits in: each member updates their own understanding of this business from
        # the exchange that just happened. Their memories are what later decisions reason from.
        await self._firm_observe(last_question, client_message)

        if self.turn >= self.max_turns:
            return await self._close()          # hard cap always wins

        # Owned completeness: before concluding, the interview MUST have walked the workflow to
        # its terminal. If the front is saturated (or we're low on turns) but the arc isn't yet
        # traversed, force the next required terminal probe instead of stopping.
        override = None
        if self._must_force_arc():
            key, prompt = next_unasked_probe(self.arc_asked)
            self.arc_asked.add(key)
            self.last_new_step_turn = self.turn   # give the newly-probed end room to surface steps
            override = prompt
        elif self._saturated() and arc_traversed(self.arc_asked):
            return await self._close()            # front done AND the whole arc mapped -> conclude

        q, self.pending_focus = await next_question(self.client, self.model, self.history,
                                                    focus_override=override)
        self.history.append({"role": "assistant", "content": q})
        return q
