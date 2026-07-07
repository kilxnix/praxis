"""LLM role-play of a scenario client, so Phase 0 can run repeatable hard interviews
without recruiting real humans."""


def SIM_SYSTEM(scenario):
    return (
        f"You are the owner of {scenario.business}. Stay fully in character.\n"
        f"How you answer: {scenario.persona}.\n"
        f"The real workflow (reveal ONLY the specific bits you're actually asked about, "
        f"in your own casual words, never as a tidy list): {scenario.truth}\n"
        f"Answer in 1-3 sentences. Never break character or explain that you are an AI."
    )


async def simulated_reply(client, scenario, interviewer_question, history):
    msgs = []
    for h in history[-6:]:
        msgs.append(h)
    msgs.append({"role": "user", "content": interviewer_question})
    return (await client.complete(SIM_SYSTEM(scenario), msgs,
                                  max_tokens=160, temperature=0.9)).strip()
