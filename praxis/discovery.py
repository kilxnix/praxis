"""Discovery agent operations: extract grounded graph deltas from a client turn,
apply them to the WorkflowModel, and ask the next gap-driven question."""
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P
from praxis.discovery_signals import canonical_label, is_valid_step_label
from praxis.plays import InterviewState, select_play, focus_target

_VALID_NODE = {t.value for t in NodeType}
_VALID_EDGE = {t.value for t in EdgeType}


async def extract_deltas(client, history, latest_msg, turn, focus=None):
    result = await client.complete_json(P.EXTRACTION_SYSTEM,
                                        P.build_extraction_user(history, latest_msg, focus))
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
    if ntype == NodeType.STEP and not is_valid_step_label(label):
        return None
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
            if src is None or tgt is None:
                continue
            model.add_edge(EdgeType(d["edge_type"]), src.id, tgt.id, [ev])
        except (KeyError, ValueError):
            continue


async def next_question(client, model, history):
    last = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last = m.get("content", "")
            break
    state = InterviewState(model, last_answer=last)
    play = select_play(state)
    hint = play.focus(state)
    intent = focus_target(state)   # which step + facet this question targets, or None
    user = P.build_interviewer_user(history, hint)
    text = await client.complete(P.INTERVIEWER_SYSTEM,
                                 [{"role": "user", "content": user}],
                                 max_tokens=120, temperature=0.45)
    return text.strip(), intent
