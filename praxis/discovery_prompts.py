"""From-scratch Discovery prompts. Voice: a sharp, personable operator who has
walked a hundred shop floors — brisk, curious, NOT therapeutic. Written fresh for
business-workflow interviews; do not port wellness prompt text (Global Constraint)."""
import json

EXTRACTION_SYSTEM = """You extract a business's workflow into a graph, using ONLY the \
person's own words as evidence. Never invent steps, tools, or people they did not mention.

Return JSON: {"deltas": [ ... ]}. Each delta is one of:
- {"op":"add_node","node_type":"step|actor|tool|artifact|friction","label":"<short, their words>","quote":"<the exact phrase that justifies it>"}
- {"op":"add_edge","edge_type":"sequence|performs|uses|produces|consumes|causes","source_label":"..","source_type":"..","target_label":"..","target_type":"..","quote":"<exact phrase>"}

Rules:
- Every delta MUST include a verbatim quote from the latest message. No quote -> do not emit it.
- Labels are short and in the speaker's vocabulary (e.g. "the order sheet", not "Order Management System").
- Only extract what THIS message adds. Do not restate the whole graph."""


def build_extraction_user(history, latest):
    recent = "\n".join(f'{m["role"]}: {m["content"]}' for m in history[-6:])
    return json.dumps({"recent_conversation": recent, "latest_client_message": latest}, indent=2)
