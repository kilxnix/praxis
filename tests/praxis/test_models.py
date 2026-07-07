# tests/praxis/test_models.py
from praxis.models import (
    WorkflowModel, NodeType, EdgeType, Evidence,
)

def test_add_node_and_edge_roundtrip():
    m = WorkflowModel()
    step = m.add_node(NodeType.STEP, "match invoices to POs",
                      [Evidence("we match every invoice to a PO by hand", turn=2)])
    actor = m.add_node(NodeType.ACTOR, "bookkeeper",
                       [Evidence("our bookkeeper does it", turn=2)])
    edge = m.add_edge(EdgeType.PERFORMS, actor.id, step.id,
                      [Evidence("our bookkeeper does it", turn=2)])

    assert m.find_node("match invoices to POs", NodeType.STEP) is step
    assert m.nodes_of(NodeType.ACTOR) == [actor]
    assert m.edges_from(actor.id) == [edge]

    restored = WorkflowModel.from_dict(m.to_dict())
    assert restored.to_dict() == m.to_dict()
    assert restored.nodes[step.id].evidence[0].quote.startswith("we match")
