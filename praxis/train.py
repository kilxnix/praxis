"""Keep the firm live — run engagements back-to-back so the five employees keep learning.

Praxis's five agents are people who develop their own minds by working businesses. After every
engagement each one distills durable, transferable lessons into firm_minds/<role>.json and carries
them into the next business. One engagement seasons them a little; this loop keeps them working,
unattended, so their minds compound over many businesses and their reasoning becomes genuinely
their own — instead of leaning on the base model every time.

    python -m praxis.train                 # run continuously, gentle pace, until Ctrl+C
    python -m praxis.train --count 20      # run 20 engagements, then stop
    python -m praxis.train --interval 30   # wait 30s between engagements (lighter on the machine)
    python -m praxis.train --shuffle       # vary the order the businesses come in
    python -m praxis.train --status        # show what each employee has learned so far, then exit

Each engagement is one full run (interview -> firm -> deliverable) on the local model; the firm
learns and atomically saves their minds after each one. Progress is appended to
firm_minds/training_log.jsonl and each employee's growing mind is firm_minds/<role>.json.
Stop any time (Ctrl+C) — minds persist, so the next run picks up seasoned. An engagement that
errors is logged and skipped; it never kills the loop.
"""
import argparse
import asyncio
import datetime
import json
import os
import random
import time

from praxis.eval.scenarios import SCENARIOS
from praxis.firm_agent import AgentMind, ROSTER
from praxis.llm_client import OllamaClient
from praxis.pipeline import run_pipeline, save_engagement

DEFAULT_MINDS_DIR = "firm_minds"
NAME = {ident.key: ident.name for ident in ROSTER}


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def business_pool():
    """The businesses the firm trains on: the built-in scenarios plus, if present, a generated
    corpus (praxis/eval/corpus.py) that widens the range of professions so learning generalizes
    toward 'any business'. The corpus is optional — the loop runs fine on the built-ins alone."""
    pool = list(SCENARIOS)
    try:
        from praxis.eval.corpus import CORPUS
        pool += list(CORPUS)
    except Exception:
        pass
    return pool


def mind_sizes(minds_dir=DEFAULT_MINDS_DIR):
    """How many lessons each employee currently carries — read from disk so it reflects the real,
    persisted mind (which the loop grows and periodically consolidates)."""
    return {ident.key: len(AgentMind.load(ident.key, minds_dir).lessons) for ident in ROSTER}


def _append_ledger(path, rec):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _format_progress(rec):
    if not rec.get("ok"):
        return f"[{rec['n']}] {rec['business']}: FAILED after {rec['seconds']}s — {rec['error']}"
    new_total = sum(v for v in rec["new"].values())
    # ASCII only: this line is printed every engagement, sometimes to a file whose encoding we
    # don't control — a UnicodeEncodeError here must never be able to kill the loop.
    sizes = " | ".join(f"{NAME[k]} {rec['minds'][k]}" for k in rec["minds"])
    return (f"[{rec['n']}] {rec['business']}: +{new_total} lesson(s) in {rec['seconds']}s"
            f"   minds -> {sizes}")


def status(minds_dir=DEFAULT_MINDS_DIR):
    """A readable snapshot of who the firm has become: how many lessons each employee carries and
    their most recent ones. This is the proof the agents are actually developing minds."""
    out = ["The firm's minds so far:\n"]
    for ident in ROSTER:
        m = AgentMind.load(ident.key, minds_dir)
        out.append(f"{ident.name} — {ident.role}: {len(m.lessons)} lesson(s)")
        for l in m.lessons[-5:]:
            out.append(f"    · {l.text}")
        out.append("")
    ledger = os.path.join(minds_dir, "training_log.jsonl")
    if os.path.exists(ledger):
        recs = [json.loads(x) for x in open(ledger, encoding="utf-8").read().splitlines() if x.strip()]
        ok = sum(1 for r in recs if r.get("ok"))
        out.append(f"Engagements worked: {len(recs)}  ({ok} completed, {len(recs) - ok} errored)")
    return "\n".join(out)


def _make_default_runner(clients, out_root, keep_engagements, max_turns):
    """The real engagement: interview (simulated owner) -> firm -> deliverable, on the local model.
    finalize() inside run_pipeline calls reflect_firm(), so the firm learns and saves their minds
    as part of this. Optionally persists the whole engagement to its own folder."""
    interviewer, sim = clients

    async def run_one(scenario):
        state = await run_pipeline(interviewer, sim, scenario,
                                   clock=time.monotonic, max_turns=max_turns)
        if keep_engagements:
            save_engagement(state, os.path.join(out_root, f"{scenario.key}_{_stamp()}"))
        return state

    return run_one


async def train(*, count=None, interval=5.0, minds_dir=DEFAULT_MINDS_DIR, out_root="engagements",
                keep_engagements=False, start=0, shuffle=False, max_turns=25, pool=None,
                run_one=None, sleep=asyncio.sleep, log=print):
    """Run engagements one after another, letting the firm learn between each.

    count      how many engagements to run (None = continuous, until interrupted)
    interval   seconds to pause between engagements (lets the machine breathe)
    minds_dir  where the employees' minds live and grow
    start      index to begin from in the business pool (for resuming variety)
    shuffle    randomize the order the businesses arrive in
    run_one    async fn(scenario) that performs one engagement; default wires the real pipeline.
               Injected in tests so the loop can be exercised without the model.

    Returns the number of engagements attempted. One-at-a-time by design — the firm reasons
    better and the machine stays usable when engagements don't run in parallel."""
    pool = pool if pool is not None else business_pool()
    if not pool:
        raise SystemExit("no businesses to train on")
    order = list(range(len(pool)))
    if shuffle:
        random.shuffle(order)

    ledger = os.path.join(minds_dir, "training_log.jsonl")
    clients = None
    if run_one is None:
        clients = (OllamaClient(), OllamaClient())
        run_one = _make_default_runner(clients, out_root, keep_engagements, max_turns)

    n = 0
    i = start
    try:
        while count is None or n < count:
            scenario = pool[order[i % len(order)]]
            before = mind_sizes(minds_dir)
            t0 = time.monotonic()
            try:
                await run_one(scenario)
                after = mind_sizes(minds_dir)
                rec = {"n": n + 1, "business": scenario.key,
                       "seconds": round(time.monotonic() - t0, 1),
                       "minds": after,
                       "new": {k: after.get(k, 0) - before.get(k, 0) for k in after},
                       "ok": True}
            except Exception as e:  # a bad engagement must never kill the loop
                rec = {"n": n + 1, "business": scenario.key,
                       "seconds": round(time.monotonic() - t0, 1),
                       "error": f"{type(e).__name__}: {e}", "ok": False}
            _append_ledger(ledger, rec)
            log(_format_progress(rec))
            n += 1
            i += 1
            if count is not None and n >= count:
                break
            await sleep(interval)
    finally:
        if clients:
            await clients[0].close()
            await clients[1].close()
    return n


def main():
    import sys
    # The firm's lessons are UTF-8 (em dashes, bullets); a Windows console defaults to cp1252 and
    # would raise UnicodeEncodeError on them. Reconfigure to UTF-8 with replacement so printing
    # a mind can never crash a long unattended run.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Keep the Praxis firm live and learning.")
    p.add_argument("--count", type=int, default=None,
                   help="how many engagements to run (default: continuous, until Ctrl+C)")
    p.add_argument("--interval", type=float, default=5.0,
                   help="seconds to pause between engagements (default 5)")
    p.add_argument("--minds-dir", default=DEFAULT_MINDS_DIR,
                   help="where the employees' minds live (default firm_minds)")
    p.add_argument("--out-root", default="engagements")
    p.add_argument("--keep-engagements", action="store_true",
                   help="also save each engagement's full folder (off by default to avoid bloat)")
    p.add_argument("--shuffle", action="store_true", help="randomize the order of businesses")
    p.add_argument("--start", type=int, default=0, help="index to begin from in the business pool")
    p.add_argument("--max-turns", type=int, default=25)
    p.add_argument("--status", action="store_true",
                   help="print what each employee has learned so far, then exit")
    args = p.parse_args()

    if args.status:
        print(status(args.minds_dir))
        return

    pool = business_pool()
    print(f"Praxis firm going live: {len(pool)} businesses in rotation, "
          f"{'continuous' if args.count is None else args.count} engagement(s), "
          f"{args.interval}s between. Ctrl+C to stop — minds persist.\n")
    try:
        worked = asyncio.run(train(count=args.count, interval=args.interval,
                                   minds_dir=args.minds_dir, out_root=args.out_root,
                                   keep_engagements=args.keep_engagements, start=args.start,
                                   shuffle=args.shuffle, max_turns=args.max_turns))
        print(f"\nDone — {worked} engagement(s) worked. Minds saved in {args.minds_dir}/.")
    except KeyboardInterrupt:
        print("\nStopped. The firm kept everything they learned — "
              f"see `python -m praxis.train --status`.")


if __name__ == "__main__":
    main()
