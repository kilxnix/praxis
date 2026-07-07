"""Discovery agent operations: extract grounded graph deltas from a client turn,
apply them to the WorkflowModel, and ask the next gap-driven question."""
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P
from praxis.coverage import analyze_coverage, biggest_gap
from praxis.discovery_signals import canonical_label, is_valid_step_label

_VALID_NODE = {t.value for t in NodeType}
_VALID_EDGE = {t.value for t in EdgeType}


async def extract_deltas(client, history, latest_msg, turn):
    result = await client.complete_json(P.EXTRACTION_SYSTEM,
                                        P.build_extraction_user(history, latest_msg))
    out = []
    for d in result.get("deltas", []):
        if not isinstance(d, dict):
            continue
        q = d.get("quote")
        quote = q.strip() if isinstance(q, str) else ""
        if not quote:
            continue
        op = d.get("op")
        try:
            if op == "add_node" and d.get("node_type") in _VALID_NODE and d.get("label"):
                if d["node_type"] == "step" and not is_valid_step_label(d["label"]):
                    continue
                out.append(d)
            elif op == "add_edge" and d.get("edge_type") in _VALID_EDGE \
                    and d.get("source_label") and d.get("target_label") \
                    and d.get("source_type") in _VALID_NODE and d.get("target_type") in _VALID_NODE:
                out.append(d)
        except TypeError:
            continue
    return out


def _get_or_add(model, label, ntype, ev):
    target = canonical_label(label)
    for n in model.nodes.values():
        if n.type == ntype and canonical_label(n.label) == target:
            n.evidence.append(ev)
            n.confidence.evidence_count += 1
            return n
    return model.add_node(ntype, label, [ev])


def apply_deltas(model, deltas, turn):
    for d in deltas:
        if d.get("op") != "add_node":
            continue
        q = d.get("quote")
        if not isinstance(q, str) or not q.strip():
            continue
        try:
            _get_or_add(model, d["label"], NodeType(d["node_type"]), Evidence(q.strip(), turn))
        except (KeyError, ValueError):
            continue
    for d in deltas:  # edges after nodes so endpoints resolve
        if d.get("op") != "add_edge":
            continue
        q = d.get("quote")
        if not isinstance(q, str) or not q.strip():
            continue
        try:
            ev = Evidence(q.strip(), turn)
            src = _get_or_add(model, d["source_label"], NodeType(d["source_type"]), ev)
            tgt = _get_or_add(model, d["target_label"], NodeType(d["target_type"]), ev)
            model.add_edge(EdgeType(d["edge_type"]), src.id, tgt.id, [ev])
        except (KeyError, ValueError):
            continue


_FACET_Q = {
    "actor": "who does it", "tool": "what tool they use",
    "input": "what they start with", "output": "what it produces",
    "friction": "what goes wrong there",
}


def focus_hint_for(model):
    rep = analyze_coverage(model)
    gap = biggest_gap(rep)
    if gap:
        wants = ", ".join(_FACET_Q[f] for f in gap.missing if f in _FACET_Q)
        return f"For the step '{gap.step_label}', find out: {wants}."
    return "Ask what happens right after the last step, or what part of this work is most painful."


async def next_question(client, model, history):
    hint = focus_hint_for(model)
    system = P.INTERVIEWER_SYSTEM
    user = P.build_interviewer_user(history, hint)
    text = await client.complete(system, [{"role": "user", "content": user}],
                                 max_tokens=120, temperature=0.7)
    return text.strip()
