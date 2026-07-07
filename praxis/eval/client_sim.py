"""LLM role-play of a scenario client, so Phase 0 can run repeatable hard interviews
without recruiting real humans."""


def SIM_SYSTEM(scenario):
    return (
        f"You role-play the owner of {scenario.business}, being interviewed about how "
        f"your business actually works.\n"
        f"You have a REAL, CONSISTENT workflow and you describe it TRUTHFULLY and "
        f"COHERENTLY. You never invent random, nonsensical, or contradictory actions — "
        f"every answer must be a real part of the workflow below.\n"
        f"YOUR REAL WORKFLOW: {scenario.truth}\n"
        f"Answer the interviewer's SPECIFIC question directly, using only that real "
        f"workflow. Give concrete detail as it is asked for, rather than dumping "
        f"everything at once. Keep answers to 1-2 sentences.\n"
        f"YOUR SPEAKING STYLE (affects tone only, never the coherence or truth of your "
        f"answer): {scenario.persona}\n"
        f"Never break character; never mention being an AI."
    )


async def simulated_reply(client, scenario, interviewer_question, history):
    msgs = []
    for h in history[-6:]:
        msgs.append(h)
    msgs.append({"role": "user", "content": interviewer_question})
    return (await client.complete(SIM_SYSTEM(scenario), msgs,
                                  max_tokens=140, temperature=0.55)).strip()
