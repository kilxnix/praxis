"""One clean entry point for a full Praxis engagement.

Praxis is the agency; the firm are real employees — they carry a personality, they morph to fit
each business, and they learn across engagements. This runs one complete engagement (interview ->
firm -> deliverable), saves it to its OWN folder under engagements/, and lets the firm keep what
they learned in firm_minds/.

    python -m praxis.run hvac_tech        # or any scenario key; defaults to hvac_tech

Each run lands in its own directory:
    engagements/<business>_<YYYYmmdd-HHMMSS>/
        deliverable.md      the client-facing plan
        engagement.json     the full record (map, transcript, every hand-off, the deliverable)
        firm/<employee>.md  who each employee became, understood, and now carries forward
"""
import asyncio
import datetime
import time

from praxis.llm_client import OllamaClient
from praxis.eval.scenarios import SCENARIOS
from praxis.pipeline import run_pipeline, save_engagement


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


async def run_engagement(scenario_key="hvac_tech", out_root="engagements", max_turns=25):
    """Run one full engagement and save it to its own timestamped folder. Returns the path."""
    sc = next((s for s in SCENARIOS if s.key == scenario_key), None)
    if sc is None:
        raise SystemExit(f"unknown scenario '{scenario_key}'; "
                         f"choose from: {', '.join(s.key for s in SCENARIOS)}")
    interviewer, sim = OllamaClient(), OllamaClient()
    try:
        state = await run_pipeline(interviewer, sim, sc, clock=time.monotonic, max_turns=max_turns)
    finally:
        await interviewer.close()
        await sim.close()
    out_dir = f"{out_root}/{scenario_key}_{_stamp()}"
    save_engagement(state, out_dir)
    return out_dir, state


def main():
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "hvac_tech"
    out_dir, state = asyncio.run(run_engagement(key))
    recs = len(state.deliverable.get("where_ai_fits", []))
    print(f"\nSaved to {out_dir}")
    print(f"  deliverable.md   ({recs} recommendation(s))")
    print(f"  engagement.json  (full record + every hand-off)")
    print(f"  firm/            (the 5 employees: who they became + what they learned)")


if __name__ == "__main__":
    main()
