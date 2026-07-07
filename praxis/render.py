"""Render a deliverable dict as a clean Markdown document — what the client reads. Leads
with the human summary and plain-language pains; each recommendation leads with the OUTCOME
for the owner, with the technical 'how' kept secondary."""


def to_markdown(deliverable, title="AI Implementation Plan"):
    d = deliverable
    out = [f"# {title}", ""]

    if d.get("summary"):
        out += [d["summary"], ""]

    out += ["## What's costing you time today", ""]
    pains = d.get("pains")
    if pains:
        for p in pains:
            out.append(f"- {p}")
    else:
        hurts = d.get("where_it_hurts", [])
        if hurts:
            for h in hurts:
                out.append(f"- **{h['step']}** — {', '.join(h['friction'])}")
        else:
            out.append("_No specific friction surfaced during discovery._")

    out += ["", "## Where AI can help (start here)", ""]
    fits = d.get("where_ai_fits", [])
    if not fits:
        out.append("_No interventions cleared review._")
    for e in fits:
        headline = e.get("outcome") or e["what_it_does"]
        out.append(f"### {e['priority'].title()} — {headline}")
        out.append(f"*effort {e['effort']} · saves {e['time_saved']} time · risk {e['risk']}*")
        out.append("")

    later = d.get("bigger_or_later", [])
    if later:
        out += ["## Bigger bets (once the quick wins land)", ""]
        for e in later:
            headline = e.get("outcome") or e["what_it_does"]
            out.append(f"- **{headline}** *(effort {e['effort']} · saves {e['time_saved']} "
                       f"time · risk {e['risk']})*")
        out.append("")

    out += ["## Suggested order (start here)", ""]
    roll = d.get("rollout", [])
    for i, s in enumerate(roll, 1):
        match = next((e for e in fits if e["step"] == s), None)
        label = (match.get("outcome") if match and match.get("outcome") else s)
        out.append(f"{i}. {label}")
    if not roll:
        out.append("_—_")

    out += ["", "## What we're not recommending (and why)", ""]
    nots = d.get("not_recommending", [])
    if nots:
        for n in nots:
            out.append(f"- **{n['step']}** — {n['reason']}")
    else:
        out.append("_Nothing set aside._")

    return "\n".join(out) + "\n"
