"""Semantic step consolidation for Discovery v3. The surface `canonical_label`
(discovery_signals) collapses article/case/plural variants; this pass uses the LLM to
merge SAME-activity steps worded differently (e.g. "write five dots" ~ "scribble five
dots"). Ocean-safe: it groups the client's OWN labels, imposing no external categories.

Merging is a pure graph transform (re-point edges to a canonical node, union evidence,
drop the duplicate); only the grouping decision uses the LLM.

After the LLM pass, an OWNED grain cleanup always runs: drop micro/vague/third-party
non-steps that slipped extraction, and merge near-duplicate steps the model left split
(e.g. three commission-spreadsheet variants). That is the fix for realtor-map noise —
we don't just note it in the audit."""
import json
import re
from praxis.models import NodeType
from praxis.discovery_signals import is_valid_step_label, canonical_label

CONSOLIDATE_SYSTEM = """You are given a list of workflow STEP labels from ONE business. \
Many describe the SAME underlying action in different words — a different verb, tense, or \
extra detail. For example "draft proposal", "type proposal manually", and "write the \
proposal" are ONE step; "copy lead into spreadsheet" and "paste details into the sheet" \
are ONE step; "check commission numbers against spreadsheet", "verify commission check \
matches spreadsheet", and "re-type final numbers into spreadsheet" are ONE step (same \
reconciliation). Group all such duplicates AGGRESSIVELY.

Return JSON {"groups": [[...], ...]}. Each group lists 2+ input labels that are the same \
step; put the shortest, clearest label FIRST (it becomes canonical). Merge steps that \
share the same core action or purpose even if worded quite differently. Do NOT group \
steps that are genuinely different actions (e.g. "draft proposal" vs "send invoice"). \
Omit any label that has no duplicate. Also omit micro-motions and third-party events \
("double-check phone", "delivers images") — those are not real owner steps."""


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


def _drop_step(model, step_id):
    """Remove a non-step node and every edge touching it."""
    if step_id not in model.nodes:
        return
    for eid in list(model.edges):
        e = model.edges[eid]
        if e.source == step_id or e.target == step_id:
            del model.edges[eid]
    del model.nodes[step_id]


# Light words ignored when comparing steps for near-duplicate merge.
_MERGE_STOP = {
    "the", "a", "an", "into", "to", "from", "on", "in", "for", "with", "against",
    "my", "our", "your", "and", "or", "of", "at", "by", "up", "out", "over",
}
# Verbs that mean the same kind of reconciliation / data-check when paired with the same object.
_VERIFY_FAMILY = {
    "check", "verify", "match", "matches", "matching", "confirm", "reconcile",
    "retype", "re-type", "type", "reenter", "re-enter", "compare", "crosscheck",
    "cross-check", "audit", "validate",
}


def _merge_signature(label):
    """Content tokens of a step, with check/verify/re-type collapsed — so near-duplicates
    of the same reconciliation land on the same signature set."""
    c = canonical_label(label)
    # "re-type" / "re-enter" become two tokens after punctuation strip — collapse first.
    c = re.sub(r"\bre\s+type\b", "retype", c)
    c = re.sub(r"\bre\s+enter\b", "reenter", c)
    c = re.sub(r"\bcross\s+check\b", "crosscheck", c)
    toks = []
    for t in c.split():
        if t in _MERGE_STOP:
            continue
        if t in _VERIFY_FAMILY or t.replace("-", "") in ("retype", "reenter", "crosscheck"):
            toks.append("*verify*")
        else:
            toks.append(t)
    return set(toks)


def _near_duplicate(a_label, b_label, min_jaccard=0.5):
    sa, sb = _merge_signature(a_label), _merge_signature(b_label)
    if not sa or not sb:
        return False
    return (len(sa & sb) / len(sa | sb)) >= min_jaccard


def _owned_merge_near_duplicates(model):
    """Deterministic merge of steps the LLM left split (commission triple, etc.).
    Uses connected components so A~B and B~C merge A+B+C even if A~C is weaker.
    Prefer the shorter label with more evidence as canonical inside each component."""
    steps = list(model.nodes_of(NodeType.STEP))
    if len(steps) < 2:
        return
    n = len(steps)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if _near_duplicate(steps[i].label, steps[j].label):
                union(i, j)

    components = {}
    for i in range(n):
        components.setdefault(find(i), []).append(steps[i])

    for group in components.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda s: (len(s.label), -s.confidence.evidence_count, s.id))
        canon = group[0]
        for dup in group[1:]:
            if dup.id in model.nodes and canon.id in model.nodes:
                _merge(model, canon.id, dup.id)


def prune_map_grain(model):
    """Owned grain cleanup — always runs after consolidate (and can be called alone).
    1. Drop steps that fail is_valid_step_label (micro-motions, umbrellas, third-party events).
    2. Merge near-duplicate remaining steps by content signature.
    Deterministic; does not invent domain categories — only FORM of the labels."""
    for s in list(model.nodes_of(NodeType.STEP)):
        if not is_valid_step_label(s.label):
            _drop_step(model, s.id)
    _owned_merge_near_duplicates(model)


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
    if len(steps) >= 3:
        labels = [s.label for s in steps]
        result = await client.complete_json(CONSOLIDATE_SYSTEM,
                                            json.dumps({"steps": labels}))
        groups = result.get("groups", []) if isinstance(result, dict) else []
        apply_groups(model, groups)
    # Always: owned grain cleanup so local-model laziness can't leave a noisy map.
    prune_map_grain(model)
