"""Render a deliverable dict as a clean Markdown document — what the client actually reads."""


def to_markdown(deliverable, title="AI Implementation Plan"):
    d = deliverable
    out = [f"# {title}", ""]

    out += ["## 1. Your workflow, as we heard it", ""]
    for s in d.get("workflow_mirror", []):
        out.append(f"- {s}")
    if not d.get("workflow_mirror"):
        out.append("_(no steps mapped)_")

    out += ["", "## 2. Where it hurts", ""]
    hurts = d.get("where_it_hurts", [])
    if hurts:
        for h in hurts:
            out.append(f"- **{h['step']}** — {', '.join(h['friction'])}")
    else:
        out.append("_No specific friction surfaced during discovery._")

    out += ["", "## 3. Where AI fits", ""]
    fits = d.get("where_ai_fits", [])
    if not fits:
        out.append("_No interventions cleared review._")
    for e in fits:
        out.append(f"### {e['priority'].title()} — {e['step']}")
        out.append(f"- **What it does:** {e['what_it_does']}")
        out.append(f"- **Where it plugs in:** {e['where_it_plugs_in']}")
        out.append(f"- **Inputs needed:** {e['inputs_needed']}")
        out.append(f"- **What changes for people:** {e['changes_for_people']}")
        out.append(f"- **Effort:** {e['effort']} · **Time saved:** {e['time_saved']} · "
                   f"**Risk:** {e['risk']}")
        if e.get("caveat"):
            out.append(f"- **Caveat (from the Skeptic):** {e['caveat']}")
        out.append("")

    out += ["## 4. Rollout order", ""]
    roll = d.get("rollout", [])
    for i, s in enumerate(roll, 1):
        out.append(f"{i}. {s}")
    if not roll:
        out.append("_—_")

    out += ["", "## 5. What we're not recommending (and why)", ""]
    nots = d.get("not_recommending", [])
    if nots:
        for n in nots:
            out.append(f"- **{n['step']}** — {n['reason']}")
    else:
        out.append("_Nothing set aside._")

    return "\n".join(out) + "\n"
