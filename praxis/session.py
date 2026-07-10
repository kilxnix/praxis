"""Drives one Discovery interview: client message -> grow graph -> next question,
until coverage is high enough or the turn cap is hit. The session owns the stop
condition (intake-completeness)."""
import re
from praxis.models import WorkflowModel, NodeType
from praxis.coverage import analyze_coverage
from praxis.discovery import extract_deltas, apply_deltas, next_question
from praxis.consolidate import consolidate_steps, prune_map_grain
from praxis.arc import REQUIRED, ARC_PROBES, next_unasked_probe, arc_traversed
from praxis.firm_agent import assemble_firm
from praxis.engagement import Fixture

# A concrete data sample worth keeping as ground truth: real numbers/IDs/money/quantities in
# the owner's answer (a part number, mileage, an amount, a code). Deterministic, owned.
_CONCRETE = re.compile(r"(?:#\s*\d|\$\s?\d|\b\d{2,}\b|\b\d+\s?(?:hrs?|hours|miles|units|%)\b)", re.I)

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
        self.probed_foci = set()    # "step|facet" already asked — never re-ask the same gap
        self._closed = False
        self.arc_asked = set()      # which required terminal probes we've asked (owned completeness)
        self.fixtures = []          # real data samples (ground truth for SP2's Verifier)
        self.core_step_labels = set()       # steps that ARE the business's core value work
        self._awaiting_core_answer = False  # the next answer replies to the core-work probe

    def opening_line(self):
        return OPENING

    async def seed_from_text(self, text, fixtures=None):
        """SEED discovery from ingested materials (documents, OCR'd photos, transcripts) so the
        interview STARTS already knowing the business and spends its questions on the GAPS the
        materials didn't cover. Ingest increases what discovery starts with — it does not replace
        the interview or the firm. `fixtures` is [(source, sample), ...] of the REAL material,
        kept as ground truth for SP2. Returns the first (gap-directed) question to ask.

        After this, drive the session normally with submit(); the plays/arc engine sees what's
        already mapped and probes what's missing (parts-ordering, invoicing, the terminal, etc.)."""
        from praxis.discovery import ingest_text_to_model   # local import: avoid a cycle
        for source, sample in (fixtures or []):
            if sample and sample.strip():
                self.fixtures.append(Fixture(sample.strip()[:2000], source))
        model, transcript = await ingest_text_to_model(self.client, text)
        self.model = model
        # Fold the materials in as prior context, then open with a gap question instead of the
        # generic opener — we already know a lot, so don't make them repeat it.
        self.history = [{"role": "assistant", "content": OPENING}]
        self.history += [{"role": "user", "content": "(from our materials) " + m["content"]}
                         for m in transcript]
        self.last_new_step_turn = 0
        q, self.pending_focus = await next_question(
            self.client, self.model, self.history, probed_foci=self.probed_foci)
        if self.pending_focus:
            key = f"{self.pending_focus.get('step_label','').strip().lower()}|" \
                  f"{self.pending_focus.get('facet','').strip().lower()}"
            self.probed_foci.add(key)
        self.history.append({"role": "assistant", "content": q})
        return q

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

    async def _close(self):
        await consolidate_steps(self.client, self.model)   # final cleanup + owned grain prune
        prune_map_grain(self.model)                        # belt-and-suspenders before handoff
        self._closed = True
        self.history.append({"role": "assistant", "content": CLOSING})
        return CLOSING

    async def submit(self, client_message):
        if self._closed:
            return CLOSING
        self.turn += 1
        self.history.append({"role": "user", "content": client_message})
        # Capture concrete real data the owner gives (a part number, mileage, an amount) as a
        # ground-truth fixture — the real I/O sample SP2's Verifier needs.
        if _CONCRETE.search(client_message or ""):
            self.fixtures.append(Fixture(client_message.strip()[:2000], "interview"))
        before = len(self.model.nodes_of(NodeType.STEP))
        labels_before = {s.label for s in self.model.nodes_of(NodeType.STEP)}
        deltas = await extract_deltas(self.client, self.history, client_message, self.turn,
                                      focus=self.pending_focus)
        apply_deltas(self.model, deltas, self.turn)
        if len(self.model.nodes_of(NodeType.STEP)) > before:
            self.last_new_step_turn = self.turn   # a new step surfaced this turn
        # Structural CORE-WORK tagging: this answer is the owner's reply to "what's the main work
        # you're paid for" — so the steps it surfaces ARE the core, whether or not they mention
        # volume ("thousands"/"hours"). Tag them so the firm prioritizes the value work by its
        # nature, not by luck of the owner's wording (measuring volume misses a designer's
        # "3-4 directions" that still takes hours).
        if self._awaiting_core_answer:
            self.core_step_labels |= ({s.label for s in self.model.nodes_of(NodeType.STEP)}
                                      - labels_before)
            self._awaiting_core_answer = False
        if self.turn % 2 == 0:
            await consolidate_steps(self.client, self.model)

        # NOTE: the firm no longer observes every turn (that was 5 LLM calls PER TURN — most of
        # the interview's cost, and it forced each agent to work in isolation). Instead they
        # STUDY the whole interview once when they convene (see firm_agent.study_firm), then
        # DELIBERATE together to determine the product. Far cheaper, and collaborative.

        if self.turn >= self.max_turns:
            return await self._close()          # hard cap always wins

        # Force the CORE-WORK probe EARLY (not just at the terminal), so the value-producing work
        # the business is built on — a photographer's culling, a lawyer's drafting — gets mapped
        # with time left to expand it, instead of the interview rat-holing on the front office
        # and never reaching the core even when the owner mentions it. This is what makes the
        # plan cover ANY business, not just its back office.
        override = None
        if "core_work" not in self.arc_asked and \
                len(self.model.nodes_of(NodeType.STEP)) >= 2 and self.turn >= 2:
            _, override = ARC_PROBES[0]           # the core_work probe
            self.arc_asked.add("core_work")
            self._awaiting_core_answer = True     # next answer's new steps ARE the core work
            self.last_new_step_turn = self.turn
        # Owned completeness: before concluding, the interview MUST have walked the workflow to
        # its terminal. If the front is saturated (or we're low on turns) but the arc isn't yet
        # traversed, force the next required terminal probe instead of stopping.
        elif self._must_force_arc():
            key, prompt = next_unasked_probe(self.arc_asked)
            self.arc_asked.add(key)
            self.last_new_step_turn = self.turn   # give the newly-probed end room to surface steps
            override = prompt
        elif self._saturated() and arc_traversed(self.arc_asked):
            return await self._close()            # front done AND the whole arc mapped -> conclude

        q, self.pending_focus = await next_question(
            self.client, self.model, self.history,
            focus_override=override, probed_foci=self.probed_foci)
        if self.pending_focus:
            key = f"{self.pending_focus.get('step_label','').strip().lower()}|" \
                  f"{self.pending_focus.get('facet','').strip().lower()}"
            self.probed_foci.add(key)
        self.history.append({"role": "assistant", "content": q})
        return q
