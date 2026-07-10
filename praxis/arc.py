"""Owned completeness — the interview must traverse the whole workflow arc before it may
conclude. We do NOT ask the LLM 'is the job fully mapped?' (it never fires and it's the model
judging). Instead the session REQUIRES that it has explicitly probed the terminal of the
business: what happens after the core work, and how the work is delivered and paid for. The
session tracks which required probes it has asked; the LLM only phrases and extracts.

Why this fixes the real failure: on an unknown business (e.g. a wedding photographer) the
interview covered intake and quit at 'shoot photography', never mapping the culling / editing /
delivery / invoicing — the bulk of the job. A turn cap and an inert LLM 'are-we-done' let that
through. Requiring the arc's terminal to be probed forces the interview to walk to the end.

The probes are content-free — they ask about UNIVERSAL phases (what comes next, how it ends,
how you get paid), never about a specific business's domain, so they don't impose categories on
the answer (Ocean Principle). The owner describes their real ending in their own words.
"""

ARC_PROBES = [
    ("core_work",
     "Now the heart of it: what is the MAIN work you are actually paid for — the making, fixing, "
     "creating, editing, or serving itself, the part that takes the most of your time or skill? "
     "Walk me through that core work step by step, especially anything you do in high volume "
     "(going through many items, producing many things)."),
    ("after_core",
     "Now walk me PAST that — once the main work is done, what is the very next thing that "
     "happens? Keep moving forward step by step toward the end of a job."),
    ("delivery_and_payment",
     "Take me to the very end of a typical job: how does the finished work get delivered or "
     "handed to the customer, and how do you actually get paid? Include anything you do to wrap "
     "up afterward."),
]

REQUIRED = [key for key, _ in ARC_PROBES]


def next_unasked_probe(asked):
    """The next required terminal probe not yet asked, or None if the arc has been traversed."""
    for key, prompt in ARC_PROBES:
        if key not in asked:
            return key, prompt
    return None


def arc_traversed(asked):
    """True once every required terminal probe has been asked — the interview reached the end."""
    return all(key in asked for key in REQUIRED)
