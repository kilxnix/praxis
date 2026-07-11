"""One command to start Praxis for testing.

    python -m praxis.serve            # preflight, start the app, open the browser
    python -m praxis.serve --check    # only run the preflight checks
    python -m praxis.serve --port 9000 --no-open

Runs the preflight checks first (Ollama up? model pulled? deps installed?) and refuses to start
with a clear message if a required piece is missing — so a tester never hits an obscure crash
mid-interview. Then it serves the browser GUI and opens it. All LLM work stays on the local
model; nothing leaves the machine.
"""
import argparse
import threading
import time
import webbrowser

from praxis.preflight import run_checks, format_report


def main():
    ap = argparse.ArgumentParser(description="Start Praxis for testing.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--check", action="store_true", help="run preflight checks and exit")
    ap.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = ap.parse_args()

    report, ready = format_report(run_checks())
    print("Praxis preflight:\n" + report + "\n")
    if args.check:
        raise SystemExit(0 if ready else 1)
    if not ready:
        print("Not ready — fix the [XX] items above, then run `python -m praxis.serve` again.")
        raise SystemExit(1)

    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"Starting Praxis at {url}")
    print("Type a business name (optionally attach documents/photos/audio), then answer the "
          "interview. A plan is saved to engagements/<name>_<timestamp>/. Ctrl+C to stop.\n")

    if not args.no_open:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("praxis.webapp:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
