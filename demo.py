"""
Vib — Wellness Conversation Demo (Terminal)

Run this to experience the wellness conversation in your terminal.

Usage:
    python demo.py
    python demo.py --no-api    # Run without Ollama
    python demo.py --debug     # Show wellness map state
"""

import argparse
import asyncio
import sys

# Enable ANSI colors on Windows
try:
    from colorama import init as colorama_init
    colorama_init()
except ImportError:
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

from interviewer.orchestrator import VibSession
from interviewer.llm_client import SoulLLMClient
from interviewer.models import Phase


# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    VIB     = "\033[38;5;216m"   # Warm orange — Vib voice
    USER    = "\033[38;5;117m"   # Soft blue — user
    DEBUG   = "\033[38;5;243m"   # Gray — debug info
    WARN    = "\033[38;5;214m"   # Orange — warnings
    SUCCESS = "\033[38;5;114m"   # Green — good signals
    HEADER  = "\033[38;5;216m"   # Warm — headers
    STAT    = "\033[38;5;183m"   # Purple — stats


def print_header():
    print(f"""
{C.HEADER}{C.BOLD}
    ╔══════════════════════════════════════╗
    ║        V I B  —  v2.0               ║
    ║      Your wellness, understood.     ║
    ╚══════════════════════════════════════╝
{C.RESET}""")


def print_debug(session: VibSession):
    """Print wellness map debug info."""
    carto = session.cartographer
    graph = session.graph

    print(f"\n{C.DEBUG}{'─' * 50}")
    print(f"  WELLNESS MAP (debug)")
    print(f"  Phase: {graph.phase.name}  |  Attunement: {graph.attunement_confidence:.2f}  |  Turn: {graph.turn_number}")
    print(f"{'─' * 50}")

    for dim in [
        "mood_baseline", "mood_volatility", "sleep_pattern",
        "hunger_relationship", "food_preferences", "risk_window_pattern",
        "movement_pattern", "social_pattern", "stressor_signals", "response_style",
    ]:
        tc = getattr(carto, dim, None)
        if tc:
            bar = "█" * int(tc.confidence * 20) + "░" * (20 - int(tc.confidence * 20))
            label = dim.replace("_", " ").title()
            print(f"  {label:.<32} [{bar}] {tc.confidence:.2f}")

    if carto.contradictions:
        print(f"\n  {C.WARN}Contradictions:{C.DEBUG}")
        for c in carto.contradictions:
            print(f"    {c.dimension}: says '{c.stated}' but shows '{c.demonstrated}'")

    if carto.post_binge_mode:
        print(f"\n  {C.WARN}Post-binge mode: {carto.post_binge_mode}  (until {carto.post_binge_until}){C.DEBUG}")

    print(f"{'─' * 50}{C.RESET}\n")


def print_status(session: VibSession):
    """Print a compact session status."""
    graph = session.graph
    readiness = session.get_soul_readiness()
    print(f"\n{C.HEADER}{C.BOLD}{'═' * 50}")
    print(f"  SESSION STATUS")
    print(f"{'═' * 50}{C.RESET}")
    print(f"  Phase:       {graph.phase.name}")
    print(f"  Attunement:  {graph.attunement_confidence:.1%}")
    print(f"  Turn:        {graph.turn_number}")
    print(f"  Sessions:    {graph.session_number}")
    print(f"  Core ready:  {readiness['core_dimensions_ready']}")
    if readiness['open_contradictions'] > 0:
        print(f"  {C.WARN}Open contradictions: {readiness['open_contradictions']}{C.RESET}")
    print()


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Vib — Wellness Conversation Demo")
    parser.add_argument("--debug", action="store_true", help="Show wellness map state")
    parser.add_argument("--no-api", action="store_true", help="Run without Ollama")
    args = parser.parse_args()

    print_header()

    # Initialize LLM
    llm_client = None
    if not args.no_api:
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            resp.raise_for_status()
            llm_client = SoulLLMClient()
            print(f"{C.DIM}  Connected to Ollama (local LLM){C.RESET}")
        except Exception:
            print(f"{C.WARN}  Could not connect to Ollama at localhost:11434.")
            print(f"  Running in offline mode (canned responses).{C.RESET}\n")
    else:
        print(f"{C.DIM}  Running in offline mode{C.RESET}")

    # Get user name
    print(f"\n{C.VIB}  Welcome. What's your name?{C.RESET}")
    name = input(f"{C.USER}  > {C.RESET}").strip()
    if not name:
        name = "Friend"

    # Create session
    session = VibSession(user_name=name, llm_client=llm_client)

    print(f"\n{C.VIB}  Hey {name}. Let's talk.{C.RESET}")
    print(f"{C.DIM}  Commands: /status  /debug  quit{C.RESET}\n")

    debug = args.debug

    # Main wellness conversation loop
    while True:
        try:
            user_input = input(f"{C.USER}  {name}: {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C.VIB}  Take care of yourself. Talk soon.{C.RESET}\n")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower == "quit":
            print(f"\n{C.VIB}  Take care of yourself. Talk soon.{C.RESET}\n")
            if debug:
                print_debug(session)
            break

        if lower == "/status":
            print_status(session)
            continue

        if lower == "/debug":
            debug = not debug
            print(f"{C.DIM}  Debug mode: {'ON' if debug else 'OFF'}{C.RESET}\n")
            if debug:
                print_debug(session)
            continue

        # Process the message through the wellness conversation
        try:
            result = await session.process_turn(user_input)
        except Exception as e:
            print(f"{C.WARN}  Error: {e}{C.RESET}")
            if llm_client:
                llm_client = None
                session.llm_client = None
            try:
                result = await session.process_turn(user_input)
            except Exception as e2:
                print(f"{C.WARN}  Fatal error: {e2}{C.RESET}\n")
                continue

        print(f"\n{C.VIB}  Vib: {result['response']}{C.RESET}\n")

        if debug:
            move = result["move"]
            print(f"{C.DEBUG}  [{move.move_type.value}] attunement={session.graph.attunement_confidence:.2f} phase={result['phase'].name}{C.RESET}")
            print_debug(session)

    # Cleanup
    if llm_client:
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
