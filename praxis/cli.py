"""Live terminal Discovery interview against local Ollama. For eyeballing the real
interaction — the human check the eval harness can't replace."""
import asyncio
import json
from praxis.llm_client import OllamaClient
from praxis.session import DiscoverySession


async def chat():
    client = OllamaClient()
    session = DiscoverySession(client)
    print("PRAXIS >", session.opening_line())
    try:
        while not session.is_intake_complete():
            msg = input("you   > ").strip()
            if msg.lower() in {"quit", "exit"}:
                break
            reply = await session.submit(msg)
            print("PRAXIS >", reply)
    finally:
        await client.close()
    print("\n--- WORKFLOW MAP ---")
    print(json.dumps(session.model.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(chat())
