"""Semantic step consolidation for Discovery v3. The surface `canonical_label`
(discovery_signals) collapses article/case/plural variants; this pass uses the LLM to
merge SAME-activity steps worded differently (e.g. "write five dots" ~ "scribble five
dots"). Ocean-safe: it groups the client's OWN labels, imposing no external categories.

Merging is a pure graph transform (re-point edges to a canonical node, union evidence,
drop the duplicate); only the grouping decision uses the LLM."""
import json
from praxis.models import NodeType

CONSOLIDATE_SYSTEM = """You are given a list of workflow STEP labels from ONE business. \
Many describe the SAME underlying action in different words — a different verb, tense, or \
extra detail. For example "draft proposal", "type proposal manually", and "write the \
proposal" are ONE step; "copy lead into spreadsheet" and "paste details into the sheet" \
are ONE step. Group all such duplicates AGGRESSIVELY.

Return JSON {"groups": [[...], ...]}. Each group lists 2+ input labels that are the same \
step; put the shortest, clearest label FIRST (it becomes canonical). Merge steps that \
share the same core action or purpose even if worded quite differently. Do NOT group \
steps that are genuinely different actions (e.g. "draft proposal" vs "send invoice"). \
Omit any label that has no duplicate."""


def _merge(model, canon_id, dup_id):
    if canon_id == dup_id:
        return
    canon = model.nodes.get(canon_id)
    dup = model.nodes.get(dup_id)
    if canon is None or dup is None:
        return
    canon.evidence.extend(dup.evidence)
    canon.confidence.evidence_count += dup.confidence.evidence_count
    for e in model.edges.values():
        if e.source == dup_id:
            e.source = canon_id
        if e.target == dup_id:
            e.target = canon_id
    del model.nodes[dup_id]
    # drop self-loops and now-duplicate edges
    seen = set()
    for eid in list(model.edges):
        e = model.edges[eid]
        if e.source == e.target:
            del model.edges[eid]
            continue
        key = (e.type, e.source, e.target)
        if key in seen:
            del model.edges[eid]
        else:
            seen.add(key)


def apply_groups(model, groups):
    """Merge each group of step labels into its first (canonical) label. Pure."""
    label_to_id = {}
    for s in model.nodes_of(NodeType.STEP):
        label_to_id.setdefault(s.label, s.id)
    for group in groups:
        if not isinstance(group, list) or len(group) < 2:
            continue
        ids = [label_to_id[l] for l in group if l in label_to_id]
        # a label may already have been merged away; re-check existence
        ids = [i for i in ids if i in model.nodes]
        if len(ids) < 2:
            continue
        canon = ids[0]
        for dup in ids[1:]:
            _merge(model, canon, dup)


async def consolidate_steps(client, model):
    steps = model.nodes_of(NodeType.STEP)
    if len(steps) < 3:
        return
    labels = [s.label for s in steps]
    result = await client.complete_json(CONSOLIDATE_SYSTEM,
                                        json.dumps({"steps": labels}))
    groups = result.get("groups", []) if isinstance(result, dict) else []
    apply_groups(model, groups)
