"""Discovery agent operations: extract grounded graph deltas from a client turn,
apply them to the WorkflowModel, and ask the next gap-driven question."""
import re
from praxis.models import WorkflowModel, NodeType, EdgeType, Evidence
from praxis import discovery_prompts as P
from praxis.discovery_signals import canonical_label, is_valid_step_label
from praxis.plays import InterviewState, select_play, focus_target
from praxis.consolidate import consolidate_steps

_VALID_NODE = {t.value for t in NodeType}
_VALID_EDGE = {t.value for t in EdgeType}


def _chunk(text, max_chunks=30):
    """Split ingested material into map-able pieces. Prefer paragraphs; fall back to grouping
    sentences so a wall-of-text still becomes several 'turns' the extractor can chew on."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if len(paras) < 3:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
        paras = [" ".join(sents[i:i + 3]) for i in range(0, len(sents), 3)] or paras
    return paras[:max_chunks]


async def ingest_text_to_model(client, text, max_chunks=30):
    """Build a WorkflowModel from ingested material (documents, transcripts, OCR'd photos) with
    NO live interviewer — chunk it, run the same grounded extraction over each piece, and
    consolidate. The firm STUDIES the resulting transcript once at convene (run_firm), not
    per-chunk, so this stays cheap. Returns (model, transcript)."""
    model = WorkflowModel()
    transcript = []
    chunks = _chunk(text, max_chunks)
    for i, chunk in enumerate(chunks, 1):
        transcript.append({"role": "user", "content": chunk})
        deltas = await extract_deltas(client, transcript, chunk, i)
        apply_deltas(model, deltas, i)
        if i % 3 == 0:
            await consolidate_steps(client, model)
    await consolidate_steps(client, model)
    return model, transcript


async def extract_deltas(client, history, latest_msg, turn, focus=None):
    result = await client.complete_json(P.EXTRACTION_SYSTEM,
                                        P.build_extraction_user(history, latest_msg, focus))
    # The local model sometimes returns a bare list of deltas instead of {"deltas": [...]}.
    if isinstance(result, dict):
        raw = result.get("deltas", [])
    elif isinstance(result, list):
        raw = result
    else:
        raw = []
    out = []
    for d in raw:
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


async def next_question(client, model, history, focus_override=None):
    if focus_override:
        hint, intent = focus_override, None      # steer to a missing phase (completeness gate)
    else:
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
