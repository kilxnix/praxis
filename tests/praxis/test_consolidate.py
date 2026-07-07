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
