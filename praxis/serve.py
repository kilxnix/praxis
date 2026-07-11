"""One command to start Praxis for testing.

    python -m praxis.serve            # preflight, start the app, open the browser
    python -m praxis.serve --check    # only run the preflight checks
    python -m praxis.serve --tunnel   # ALSO expose a public https URL via a Cloudflare tunnel
    python -m praxis.serve --port 9000 --no-open

Runs the preflight checks first (Ollama up? model pulled? deps installed?) and refuses to start
with a clear message if a required piece is missing — so a tester never hits an obscure crash
mid-interview. Then it serves the browser GUI and opens it. All LLM work stays on the local
model; the interview and the firm run on THIS machine even when reached through the tunnel.

--tunnel note: it needs `cloudflared` on PATH (https://developers.cloudflare.com/cloudflare-one/
connections/connect-networks/downloads/). The quick tunnel gives a random public URL anyone with
the link can use — it drives YOUR local model, so only share it while you're testing.
"""
import argparse
import atexit
import shutil
import subprocess
import threading
import time
import webbrowser

from praxis.preflight import run_checks, format_report


def _start_tunnel(port):
    """Launch a Cloudflare quick tunnel to the local server. cloudflared prints its public
    https URL to stderr; we inherit its output so the tester sees the link. Returns the process
    (terminated on exit) or None if cloudflared isn't installed."""
    exe = shutil.which("cloudflared")
    if not exe:
        print("  [--] --tunnel skipped: cloudflared not found on PATH. Install it from "
              "https://developers.cloudflare.com/.../downloads/ and retry.\n")
        return None
    print("Opening a Cloudflare tunnel — watch for the public https URL below "
          "(the trycloudflare.com line):\n")
    proc = subprocess.Popen([exe, "tunnel", "--url", f"http://127.0.0.1:{port}"])
    atexit.register(lambda: proc.terminate())
    return proc


def main():
    ap = argparse.ArgumentParser(description="Start Praxis for testing.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--check", action="store_true", help="run preflight checks and exit")
    ap.add_argument("--no-open", action="store_true", help="don't open the browser")
    ap.add_argument("--tunnel", action="store_true",
                    help="expose a public https URL via a Cloudflare quick tunnel")
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

    if args.tunnel:
        _start_tunnel(args.port)

    if not args.no_open and not args.tunnel:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("praxis.webapp:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
