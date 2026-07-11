import pytest
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis.consolidate import apply_groups, consolidate_steps


def _ev():
    return [Evidence("q", 1)]


def test_apply_groups_merges_duplicates_and_repoints_edges():
    m = WorkflowModel()
    s1 = m.add_node(NodeType.STEP, "write dots", _ev())
    s2 = m.add_node(NodeType.STEP, "scribble dots", _ev())
    m.add_node(NodeType.STEP, "bake bread", _ev())
    tool = m.add_node(NodeType.TOOL, "notebook", _ev())
    m.add_edge(EdgeType.USES, s2.id, tool.id, _ev())   # edge on the duplicate
    apply_groups(m, [["write dots", "scribble dots"]])
    assert len(m.nodes_of(NodeType.STEP)) == 2          # s2 merged into s1
    assert m.nodes.get(s2.id) is None
    uses = [e for e in m.edges.values() if e.type == EdgeType.USES]
    assert len(uses) == 1 and uses[0].source == s1.id   # edge re-pointed to canonical


def test_apply_groups_ignores_singletons_and_unknown_labels():
    m = WorkflowModel()
    for lbl in ("a step", "b step", "c step"):
        m.add_node(NodeType.STEP, lbl, _ev())
    apply_groups(m, [["a step"], ["x", "y"]])           # singleton + unknown labels
    assert len(m.nodes_of(NodeType.STEP)) == 3          # nothing merged


class _FakeClient:
    def __init__(self, groups):
        self.groups = groups
    async def complete_json(self, system, user, **kw):
        return {"groups": self.groups}


@pytest.mark.asyncio
async def test_consolidate_steps_merges_via_client():
    m = WorkflowModel()
    for lbl in ("write dots", "scribble dots", "bake bread"):
        m.add_node(NodeType.STEP, lbl, _ev())
    await consolidate_steps(_FakeClient([["write dots", "scribble dots"]]), m)
    assert len(m.nodes_of(NodeType.STEP)) == 2


@pytest.mark.asyncio
async def test_consolidate_steps_noop_under_three_steps():
    m = WorkflowModel()
    m.add_node(NodeType.STEP, "only step", _ev())
    await consolidate_steps(_FakeClient([["only step", "whatever"]]), m)
    assert len(m.nodes_of(NodeType.STEP)) == 1


def test_prune_map_grain_drops_noise_and_merges_commission_triple():
    """Owned cleanup for the residential_realtor failure: drop micro/umbrella/third-party
    steps and collapse three commission-spreadsheet variants into one."""
    from praxis.consolidate import prune_map_grain
    m = WorkflowModel()
    keepers = [
        "pick best shots from photos",
        "write MLS description",
        "schedule showings on calls",
        "fill out DocuSign templates",
    ]
    noise = [
        "double-check phone after hanging up",
        "manage existing pipeline",
        "get properties listed",
        "delivers images",
    ]
    commission = [
        "re-type final numbers into spreadsheet",
        "check commission numbers against spreadsheet",
        "verify commission check matches spreadsheet",
    ]
    for lbl in keepers + noise + commission:
        m.add_node(NodeType.STEP, lbl, _ev())
    prune_map_grain(m)
    labels = {s.label for s in m.nodes_of(NodeType.STEP)}
    for n in noise:
        assert n not in labels, f"noise step should be dropped: {n}"
    for k in keepers:
        assert k in labels, f"keeper should survive: {k}"
    # Exactly one of the three commission variants remains
    left = labels & set(commission)
    assert len(left) == 1, f"commission triple should collapse to 1, got {left}"


@pytest.mark.asyncio
async def test_consolidate_always_runs_owned_prune_even_without_llm_groups():
    from praxis.consolidate import consolidate_steps
    m = WorkflowModel()
    for lbl in ("pick best shots", "write description", "delivers images",
                "manage existing pipeline"):
        m.add_node(NodeType.STEP, lbl, _ev())
    await consolidate_steps(_FakeClient([]), m)   # LLM returns no groups
    labels = {s.label for s in m.nodes_of(NodeType.STEP)}
    assert "delivers images" not in labels
    assert "manage existing pipeline" not in labels
    assert "pick best shots" in labels
