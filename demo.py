"""
The Soul — Interactive Demo

Run this to experience the Interviewer firsthand.
This is also what you'd demo for investors.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python demo.py

    # Or with a name:
    python demo.py --name "Sheltron"

    # Debug mode shows internal state:
    python demo.py --debug
"""

import argparse
import sys
import os

# Add the interviewer package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "interviewer"))

from interviewer.orchestrator import InterviewerSession
from interviewer.llm_client import SoulLLMClient
from interviewer.models import Phase, EmotionalTemperature, MoveType


# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────

# Terminal colors
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    
    SOUL    = "\033[38;5;183m"   # Soft purple — the agent's voice
    USER    = "\033[38;5;117m"   # Soft blue — the user
    DEBUG   = "\033[38;5;243m"   # Gray — internal state
    WARN    = "\033[38;5;214m"   # Orange — warnings
    SUCCESS = "\033[38;5;114m"   # Green — good signals
    HEADER  = "\033[38;5;219m"   # Pink — headers
    

def print_header():
    print(f"""
{C.HEADER}{C.BOLD}
    ╔══════════════════════════════════════╗
    ║            T H E   S O U L          ║
    ║         Interviewer  v0.1           ║
    ╚══════════════════════════════════════╝
{C.RESET}""")


def print_debug_state(result: dict, session: InterviewerSession):
    """Print internal state for debugging — the behind-the-curtain view."""
    move = result["move"]
    analysis = result["analysis"]
    graph = session.graph
    carto = session.cartographer

    print(f"\n{C.DEBUG}{'─' * 50}")
    print(f"  INTERNAL STATE (turn {graph.turn_number})")
    print(f"{'─' * 50}")
    
    # Move info
    move_name = move.move_type.value.upper().replace("_", " ")
    print(f"  Move: {C.BOLD}{move_name}{C.RESET}{C.DEBUG}")
    if move.target_dimension:
        print(f"  Targeting: {move.target_dimension}")
    if move.thread_reference:
        print(f"  Thread: {move.thread_reference}")
    print(f"  Reasoning: {move.reasoning}")

    # Emotional state
    temp = graph.temperature.value
    temp_color = {
        "cold": "\033[38;5;39m",
        "cool": "\033[38;5;117m", 
        "warm": "\033[38;5;214m",
        "hot": "\033[38;5;196m",
        "volatile": "\033[38;5;201m",
    }.get(temp, C.DEBUG)
    print(f"\n  Temperature: {temp_color}{temp}{C.DEBUG} ({graph.temperature_trend})")
    print(f"  Energy: {'█' * int(graph.energy_level * 10)}{'░' * (10 - int(graph.energy_level * 10))} {graph.energy_level:.1f}")
    print(f"  Trust:  {'█' * int(graph.trust_score * 10)}{'░' * (10 - int(graph.trust_score * 10))} {graph.trust_score:.2f}")
    print(f"  Phase:  {graph.phase.name}")

    # Open threads
    if graph.open_threads:
        print(f"\n  Open threads:")
        for t in graph.open_threads[:3]:
            weight_bar = "●" * int(t.emotional_weight * 5)
            print(f"    • {t.topic} [{weight_bar}]")

    # Cartographer signals from this turn
    signals = analysis.get("trait_signals", [])
    if signals:
        print(f"\n  Trait signals detected:")
        for s in signals:
            direction = "↑" if s.get("direction", 0) > 0 else "↓"
            stype = "D" if s.get("type") == "demonstrated" else "S"
            print(f"    {direction} {s['dimension']} [{stype}] — {s.get('signal', '')[:50]}")

    # Contradictions
    if carto.contradictions:
        print(f"\n  {C.WARN}Contradictions:{C.DEBUG}")
        for c in carto.contradictions:
            status = "✓ explored" if c.explored else "○ pending"
            print(f"    {status}: {c.dimension} — says '{c.stated}' but shows '{c.demonstrated}'")

    # Top needs
    if carto.needs[:3]:
        print(f"\n  Cartographer needs:")
        for n in carto.needs[:3]:
            print(f"    {n.dimension}: confidence={n.current_confidence:.2f}, priority={n.priority:.3f}")

    # Validation
    validation = result.get("validation")
    if validation and not validation["valid"]:
        print(f"\n  {C.WARN}Validation issues: {validation['issues']}{C.DEBUG}")

    print(f"{'─' * 50}{C.RESET}\n")


def print_soul_readiness(session: InterviewerSession):
    """Print the Soul readiness report."""
    report = session.get_soul_readiness()
    
    print(f"\n{C.HEADER}{C.BOLD}{'═' * 50}")
    print(f"  SOUL READINESS REPORT")
    print(f"{'═' * 50}{C.RESET}\n")
    
    print(f"  Sessions completed: {report['sessions_completed']}")
    print(f"  Current phase: {report['phase']}")
    print(f"  Trust level: {report['trust_level']}")
    print(f"  Overall confidence: {report['overall_confidence']}")
    print(f"  Core ready: {'✓' if report['core_dimensions_ready'] else '✗'}")
    print(f"  Matchable: {'✓' if report['matchable'] else '✗'}")
    
    print(f"\n  Dimensions:")
    for dim, conf in report["dimensions"].items():
        bar = "█" * int(conf * 20) + "░" * (20 - int(conf * 20))
        label = dim.replace("_", " ").title()
        status = C.SUCCESS if conf > 0.6 else C.WARN if conf > 0.3 else C.DEBUG
        print(f"    {status}{label:.<30} [{bar}] {conf:.2f}{C.RESET}")

    if report["open_contradictions"] > 0:
        print(f"\n  {C.WARN}⚠ {report['open_contradictions']} unexplored contradiction(s){C.RESET}")
    
    print()


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="The Soul — Interviewer Demo")
    parser.add_argument("--name", type=str, default=None, help="Your name")
    parser.add_argument("--debug", action="store_true", help="Show internal state")
    parser.add_argument("--no-api", action="store_true", help="Run without API (shows move selection only)")
    args = parser.parse_args()

    print_header()

    # Initialize LLM client
    llm_client = None
    if not args.no_api:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"{C.WARN}  No ANTHROPIC_API_KEY found in environment.")
            print(f"  Run with --no-api to see move selection without LLM generation.")
            print(f"  Or: export ANTHROPIC_API_KEY='sk-ant-...'{C.RESET}\n")
            sys.exit(1)
        
        llm_client = SoulLLMClient(api_key=api_key)
        print(f"{C.DIM}  Connected to Anthropic API (Opus 4.6){C.RESET}")
    else:
        print(f"{C.DIM}  Running in offline mode — showing move decisions only{C.RESET}")

    # Get user name
    name = args.name
    if not name:
        print(f"\n{C.SOUL}  Before we start — what should I call you?{C.RESET}")
        name = input(f"{C.USER}  > {C.RESET}").strip()
        if not name:
            name = "friend"

    # Create session
    session = InterviewerSession(user_name=name, llm_client=llm_client)

    print(f"\n{C.DIM}  Type 'quit' to exit")
    print(f"  Type '/status' to see your Soul readiness")
    print(f"  Type '/debug' to toggle debug mode")
    print(f"  Type '/newsession' to simulate returning for a new session{C.RESET}\n")

    debug = args.debug

    # Opening — the agent initiates
    if llm_client:
        # Generate a natural opening
        from interviewer.prompt_builder import BASE_SYSTEM_PROMPT, PHASE_PROMPTS, MOVE_STYLE_GUIDES
        from interviewer.models import Phase, MoveType

        opening_prompt = {
            "system": (
                BASE_SYSTEM_PROMPT + "\n\n" + 
                PHASE_PROMPTS[Phase.FIRST_CONTACT] + "\n\n" +
                MOVE_STYLE_GUIDES[MoveType.OPEN_DOOR] + "\n\n" +
                f"The user's name is {name}. This is your very first interaction. "
                f"Generate a warm, natural opening. Introduce the vibe — you're here "
                f"to get to know them. Don't be formal. Don't explain the system. "
                f"Just be a presence they want to talk to. 2-3 sentences max."
            ),
            "messages": [],
        }
        opening = llm_client.interviewer_generate(
            system=opening_prompt["system"],
            messages=[{"role": "user", "content": f"[Start conversation with {name}]"}],
        )
        print(f"{C.SOUL}  {opening}{C.RESET}\n")
        session.conversation_history.append({"role": "assistant", "content": opening})
    else:
        print(f"{C.SOUL}  Hey {name}. I'm glad you're here.{C.RESET}")
        print(f"{C.SOUL}  [OPEN_DOOR — first contact opening]{C.RESET}\n")

    # Conversation loop
    while True:
        user_input = input(f"{C.USER}  {name}: {C.RESET}").strip()

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print(f"\n{C.SOUL}  Thanks for talking with me, {name}. See you next time.{C.RESET}\n")
            print_soul_readiness(session)
            break

        if user_input.lower() == "/status":
            print_soul_readiness(session)
            continue

        if user_input.lower() == "/debug":
            debug = not debug
            print(f"{C.DIM}  Debug mode: {'ON' if debug else 'OFF'}{C.RESET}\n")
            continue

        if user_input.lower() == "/newsession":
            session.start_new_session()
            print(f"{C.DIM}  ── New session started (#{session.graph.session_number}) ──{C.RESET}\n")
            if llm_client:
                # Generate a returning-user greeting
                callback_prompt = (
                    BASE_SYSTEM_PROMPT + "\n\n" +
                    PHASE_PROMPTS.get(session.graph.phase, "") + "\n\n" +
                    f"The user ({name}) is returning for session #{session.graph.session_number}. "
                    f"Welcome them back naturally. If there are open threads from previous "
                    f"sessions, you might reference one. Keep it warm and brief."
                )
                threads_context = ""
                if session.graph.open_threads:
                    threads_context = "\nOpen threads from last time: " + ", ".join(
                        t.topic for t in session.graph.open_threads[:3]
                    )
                greeting = llm_client.interviewer_generate(
                    system=callback_prompt + threads_context,
                    messages=[{"role": "user", "content": f"[{name} has returned]"}],
                )
                print(f"{C.SOUL}  {greeting}{C.RESET}\n")
                session.conversation_history.append({"role": "assistant", "content": greeting})
            else:
                print(f"{C.SOUL}  Hey, welcome back.{C.RESET}\n")
            continue

        # Process the turn
        result = session.process_turn(user_input)

        # Show debug state if enabled
        if debug:
            print_debug_state(result, session)

        # Show the response
        print(f"\n{C.SOUL}  {result['response']}{C.RESET}\n")


if __name__ == "__main__":
    main()
