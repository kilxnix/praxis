"""SP1 must produce output SP2 can safely build on: compilable interventions (trigger/IO/
success-criteria), no no-ops in the plan, and REAL fixtures as ground truth for the Airlock."""
import pytest
from praxis.models import WorkflowModel, NodeType, Evidence
from praxis.architect import Intervention, _parse_interventions
from praxis.principal import assemble_deliverable
from praxis.business_case import Assessment
from praxis.skeptic import Verdict, ground_verdicts
from praxis.engagement import EngagementState, Fixture
from praxis.analyst import Opportunity


# --- 1. Intervention is a compilable spec -----------------------------------------------------

def test_intervention_buildable_requires_the_full_spec():
    full = Intervention("s", "does it", "here", "inputs", "changes",
                        trigger="a photo is taken", input_source="the phone photo",
                        output_dest="the QuickBooks entry",
                        success_criteria="entry matches the ticket, no blank field")
    assert full.is_buildable() is True
    prose_only = Intervention("s", "does it", "here", "inputs", "changes")
    assert prose_only.is_buildable() is False        # no trigger/IO/criteria -> not buildable


@pytest.mark.asyncio
async def test_parse_reads_the_buildable_spec_fields():
    result = {"interventions": [{
        "step_label": "type into QuickBooks", "what_it_does": "auto-enters the ticket",
        "where_it_plugs_in": "QuickBooks", "inputs_needed": "the ticket photo",
        "changes_for_people": "no typing", "trigger": "the work order photo is taken",
        "input_source": "the phone camera photo", "output_dest": "the QuickBooks invoice",
        "success_criteria": "invoice fields match the ticket"}]}
    ivs = _parse_interventions(result, {"type into QuickBooks"})
    assert ivs[0].trigger == "the work order photo is taken"
    assert ivs[0].output_dest == "the QuickBooks invoice"
    assert ivs[0].is_buildable() is True


# --- 2. No-op gate: an inert design never reaches the plan -------------------------------------

def test_noop_intervention_is_gated_out_of_the_deliverable():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "write notes", [Evidence("I write notes", 1)])
    m.add_node(NodeType.STEP, "type invoice", [Evidence("I type the invoice", 2)])
    ivs = [
        Intervention("write notes", "it simply sits idle and you still type it later", "x", "y", "z"),
        Intervention("type invoice", "reads the ticket and enters every line for you", "qb", "ticket",
                     "no typing", trigger="job done", input_source="ticket",
                     output_dest="QuickBooks", success_criteria="matches ticket"),
    ]
    scores = [Assessment("write notes", "low", "high", "low", "low", "quick win", ""),
              Assessment("type invoice", "low", "high", "low", "low", "quick win", "")]
    verds = [Verdict("write notes", "solid", ""), Verdict("type invoice", "solid", "")]
    d = assemble_deliverable(m, [], ivs, scores, verds)
    steps = [e["step"] for e in d["where_ai_fits"]]
    assert "write notes" not in steps                # the no-op was gated out
    assert "type invoice" in steps
    rec = next(e for e in d["where_ai_fits"] if e["step"] == "type invoice")
    assert rec["buildable"] is True                  # buildable spec carried into the deliverable


# --- 3. ground_verdicts catches the "hard gate/boundary" framing (photographer culling) --------

def test_ground_verdicts_overturns_hard_gate_rejection_of_core_work():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "cull thousands of images",
               [Evidence("I cull thousands of images for hours after every wedding", 3)])
    vs = [Verdict("cull thousands of images", "reject",
                  "violates the owner's hard gate requiring temporal separation between phases")]
    out = ground_verdicts(vs, m)
    assert out[0].verdict == "solid"                 # invented boundary on high-burden core -> overturned


# --- 4. Fixtures: real ground truth flows to the engagement record -----------------------------

def test_engagement_serializes_fixtures():
    st = EngagementState()
    st.fixtures = [Fixture("work order #4471: Honda Civic, brake pads, 98420 mi", "work_order.png"),
                   Fixture("part #BP-233, $84.50", "interview")]
    d = st.to_dict()
    assert len(d["fixtures"]) == 2
    assert d["fixtures"][0]["source"] == "work_order.png"
    assert "98420" in d["fixtures"][0]["sample"]


# --- 5. Session captures concrete interview data as fixtures -----------------------------------

class _NoDeltaClient:
    async def complete_json(self, system, user, **kw):
        return {"deltas": []}
    async def complete(self, system, messages, **kw):
        return "and then what?"


@pytest.mark.asyncio
async def test_session_captures_concrete_answers_as_fixtures():
    from praxis.session import DiscoverySession
    s = DiscoverySession(_NoDeltaClient(), max_turns=5, live_firm=False)
    await s.submit("a typical work order is #4471, Honda Civic, 98,420 miles, 2.5 hrs labor")
    assert len(s.fixtures) == 1                       # concrete data -> captured
    assert "4471" in s.fixtures[0].sample and s.fixtures[0].source == "interview"
    await s.submit("we just handle whatever comes in")   # no concrete data
    assert len(s.fixtures) == 1                       # vague answer -> not captured


@pytest.mark.asyncio
async def test_seed_stores_ingested_materials_as_fixtures():
    from praxis.session import DiscoverySession
    s = DiscoverySession(_NoDeltaClient(), live_firm=False)
    await s.seed_from_text("we take orders and file paper",
                           fixtures=[("work_order.png", "Maria Delgado, Honda Civic, brake pads")])
    assert any(f.source == "work_order.png" and "Maria" in f.sample for f in s.fixtures)


# --- 6. The explicit SP1->SP2 build handoff ---------------------------------------------------

def test_build_handoff_separates_buildable_from_prose_and_carries_fixtures():
    from praxis.pipeline import build_handoff
    st = EngagementState()
    st.fixtures = [Fixture("work order #4471: Honda Civic, brake pads, 98420", "work_order.png")]
    st.deliverable = {"summary": "You lose hours re-typing tickets.", "where_ai_fits": [
        {"step": "type invoice", "what_it_does": "auto-enters", "buildable": True,
         "trigger": "job done", "input_source": "ticket", "output_dest": "QuickBooks",
         "success_criteria": "matches ticket"},
        {"step": "vague thing", "what_it_does": "helps somehow", "buildable": False},
    ]}
    h = build_handoff(st)
    assert [b["step"] for b in h["buildable_interventions"]] == ["type invoice"]
    assert h["not_yet_buildable"] == ["vague thing"]          # prose-only kept out of the build set
    assert h["buildable_interventions"][0]["trigger"] == "job done"
    assert len(h["fixtures"]) == 1
    assert h["ready_for_sp2"] is True                        # has a buildable spec AND ground truth


def test_build_handoff_not_ready_without_fixtures():
    from praxis.pipeline import build_handoff
    st = EngagementState()
    st.deliverable = {"where_ai_fits": [
        {"step": "x", "buildable": True, "trigger": "t", "input_source": "i",
         "output_dest": "o", "success_criteria": "c"}]}
    assert build_handoff(st)["ready_for_sp2"] is False       # no fixtures -> Airlock has no ground truth


# --- 7. Skeptic can't reject grounded high-burden core work as "invented need" ----------------

def test_ground_verdicts_overturns_invented_need_rejection_of_core_work():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "cull images in Lightroom",
               [Evidence("I cull thousands of images for hours after every wedding", 3)])
    vs = [Verdict("cull images in Lightroom", "reject",
                  "the change invents a need for file management automation")]
    out = ground_verdicts(vs, m)
    assert out[0].verdict == "solid"                 # measured-high grounded core -> not "invented"


def test_ground_verdicts_keeps_invented_need_rejection_when_it_names_a_real_risk():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "cull images in Lightroom",
               [Evidence("I cull thousands of images for hours after every wedding", 3)])
    vs = [Verdict("cull images in Lightroom", "reject",
                  "invents a need but really the OCR could delete the wrong keeper photos")]
    out = ground_verdicts(vs, m)
    assert out[0].verdict == "reject"                # names a concrete risk (delete/wrong) -> stands


# --- 8. High-burden core work ships as a real design, not "needs scoping" --------------------

def test_high_burden_timid_design_is_replaced_with_shippable_recommendation():
    """When the local model only produces a timid design for the biggest opportunity (culling),
    the principal promotes an owned AI-first-pass design into the plan — buildable, not 'TBD'."""
    from praxis.architect import Intervention
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "cull images", [Evidence("I cull thousands of images", 1)])
    opps = [Opportunity("cull images", "cull", "sort thousands", "I cull thousands", "high")]
    ivs = [Intervention("cull images", "acts as a silent observer that does not delete", "x", "y", "z")]
    scores = [Assessment("cull images", "low", "high", "low", "low", "quick win", "")]
    verds = [Verdict("cull images", "solid", "")]
    d = assemble_deliverable(m, opps, ivs, scores, verds)
    rec = next(e for e in d["where_ai_fits"] if e["step"] == "cull images")
    assert rec["buildable"] is True
    assert "shortlist" in rec["what_it_does"].lower() or "first-pass" in rec["what_it_does"].lower() \
        or "first pass" in rec["what_it_does"].lower() or "scores" in rec["what_it_does"].lower()
    assert not any(n["step"] == "cull images" for n in d["not_recommending"])
    assert "needs more scoping" not in " ".join(n.get("reason", "") for n in d["not_recommending"])


def test_creative_generation_not_left_in_not_recommending():
    """Designer failure: high-severity sketch + Illustrator land in not_recommending after
    timid/dormant designs or paper-medium objections. Must ship as buildable first-pass."""
    from praxis.architect import Intervention
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "sketch concepts on paper",
               [Evidence("I sketch concepts on paper for hours every project", 2)])
    m.add_node(NodeType.STEP, "make changes in Illustrator",
               [Evidence("I spend hours making changes in Illustrator from markups", 3)])
    opps = [
        Opportunity("sketch concepts on paper",
                    "generate first-draft creative or professional work",
                    "Generate concept variations", "I sketch concepts on paper", "high"),
        Opportunity("make changes in Illustrator",
                    "generate first-draft creative",
                    "Apply markups as first pass", "making changes in Illustrator", "high"),
    ]
    ivs = [
        Intervention("sketch concepts on paper",
                     "Generates digital wireframes in Illustrator", "Illustrator", "brief",
                     "forces digital", trigger="t", input_source="i", output_dest="o",
                     success_criteria="c"),
        Intervention("make changes in Illustrator",
                     "Remains dormant. It does not scan PDFs or flag errors.",
                     "x", "y", "z", trigger="t", input_source="i", output_dest="o",
                     success_criteria="c"),
    ]
    scores = [Assessment(o.step_label, "low", "high", "low", "low", "quick win", "")
              for o in opps]
    verds = [
        Verdict("sketch concepts on paper", "reject",
                "forces the owner into a hybrid workflow; step is sketching on paper; "
                "replacing tactile sketching with premature software"),
        Verdict("make changes in Illustrator", "reject",
                "The change proposes remaining dormant; offers no utility"),
    ]
    d = assemble_deliverable(m, opps, ivs, scores, verds)
    steps = {e["step"] for e in d["where_ai_fits"]}
    assert "sketch concepts on paper" in steps
    assert "make changes in Illustrator" in steps
    for label in ("sketch concepts on paper", "make changes in Illustrator"):
        rec = next(e for e in d["where_ai_fits"] if e["step"] == label)
        assert rec["buildable"] is True
        assert "dormant" not in rec["what_it_does"].lower()
    assert not any(n["step"] == "sketch concepts on paper" for n in d["not_recommending"])
    assert not any(n["step"] == "make changes in Illustrator" for n in d["not_recommending"])


def test_ground_verdicts_overturns_paper_medium_rejection_of_creative_core():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "sketch concepts on paper",
               [Evidence("I sketch concepts on paper for hours every project", 2)])
    opps = [Opportunity("sketch concepts on paper", "generate first-draft creative",
                        "concepts", "I sketch concepts", "high")]
    vs = [Verdict("sketch concepts on paper", "reject",
                  "forces the owner into a hybrid workflow for a step explicitly defined as "
                  "sketching on paper; replaces tactile sketching")]
    out = ground_verdicts(vs, m, opportunities=opps)
    assert out[0].verdict == "solid"


# --- 9. Core value work is prioritized by its NATURE, not by volume words ---------------------

@pytest.mark.asyncio
async def test_core_step_is_high_severity_even_without_volume_words():
    # 'create digital drafts' has no volume words -> would measure LOW burden. But it's tagged as
    # core work (from the core-work probe), so it must come out HIGH severity and be flagged even
    # if the Analyst tries to dismiss it.
    from praxis.analyst import find_opportunities
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "create digital drafts", [Evidence("I build the drafts", 1)])
    m.add_node(NodeType.STEP, "check inbox", [Evidence("I check email", 2)])

    class DismissesCoreClient:
        """Analyst flags only the admin step and marks the core as no_fit (the bias)."""
        async def complete_json(self, system, user, **kw):
            if "did NOT evaluate" in user or "CORE work or heaviest" in user:
                return {"opportunities": [
                    {"step_label": "create digital drafts", "capability": "generate",
                     "description": "AI drafts first concepts", "evidence": "I build the drafts"}]}
            return {"opportunities": [
                {"step_label": "check inbox", "capability": "triage",
                 "description": "sort mail", "evidence": "I check email"},
                {"step_label": "create digital drafts", "no_fit": True}]}   # core wrongly dismissed

    opps = await find_opportunities(DismissesCoreClient(), m,
                                    core_steps={"create digital drafts"})
    by = {o.step_label: o for o in opps}
    assert "create digital drafts" in by                       # core rescued despite no_fit
    assert by["create digital drafts"].severity == "high"      # floored high by its core nature
