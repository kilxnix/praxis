"""Discovery agent operations: extract grounded graph deltas from a client turn,
apply them to the WorkflowModel, and ask the next gap-driven question."""
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P

_VALID_NODE = {t.value for t in NodeType}
_VALID_EDGE = {t.value for t in EdgeType}


async def extract_deltas(client, history, latest_msg, turn):
    result = await client.complete_json(P.EXTRACTION_SYSTEM,
                                        P.build_extraction_user(history, latest_msg))
    out = []
    for d in result.get("deltas", []):
        quote = (d.get("quote") or "").strip()
        if not quote:
            continue  # evidence-required: drop
        if d.get("op") == "add_node" and d.get("node_type") in _VALID_NODE and d.get("label"):
            out.append(d)
        elif d.get("op") == "add_edge" and d.get("edge_type") in _VALID_EDGE \
                and d.get("source_label") and d.get("target_label"):
            out.append(d)
    return out


def _get_or_add(model, label, ntype, ev):
    existing = model.find_node(label, ntype)
    if existing:
        existing.evidence.append(ev)
        existing.confidence.evidence_count += 1
        return existing
    return model.add_node(ntype, label, [ev])


def apply_deltas(model, deltas, turn):
    for d in deltas:
        ev = Evidence(d["quote"].strip(), turn)
        if d["op"] == "add_node":
            _get_or_add(model, d["label"], NodeType(d["node_type"]), ev)
    for d in deltas:  # edges after nodes so endpoints resolve
        if d["op"] != "add_edge":
            continue
        ev = Evidence(d["quote"].strip(), turn)
        src = _get_or_add(model, d["source_label"], NodeType(d["source_type"]), ev)
        tgt = _get_or_add(model, d["target_label"], NodeType(d["target_type"]), ev)
        model.add_edge(EdgeType(d["edge_type"]), src.id, tgt.id, [ev])
