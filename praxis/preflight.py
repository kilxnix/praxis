"""Preflight checks so a tester knows their setup is ready BEFORE the pipeline runs — a clear
'here's what's missing and how to fix it' instead of an obscure crash mid-interview.

Run:  python -m praxis.preflight        (just check)
It is also run automatically by `python -m praxis.serve` before the server starts.
"""
import importlib.util
import os

import httpx

from praxis.llm_client import DEFAULT_MODEL

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


class Check:
    def __init__(self, name, ok, detail, fix="", required=True):
        self.name, self.ok, self.detail, self.fix, self.required = name, ok, detail, fix, required


def _dep(mod, pip_name=None, required=True, note=""):
    present = importlib.util.find_spec(mod) is not None
    return Check(
        f"Python package: {pip_name or mod}",
        present,
        "installed" if present else ("missing" + (f" — {note}" if note else "")),
        fix=f"pip install {pip_name or mod}",
        required=required,
    )


def check_ollama():
    """Is the local model server up, and is the configured model pulled?"""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception as e:
        return [
            Check("Ollama server", False, f"not reachable at {OLLAMA_URL} ({type(e).__name__})",
                  fix="Install Ollama (https://ollama.com) and run it, then retry."),
            Check(f"Model '{DEFAULT_MODEL}'", False, "can't check — Ollama is down",
                  fix=f"ollama pull {DEFAULT_MODEL}"),
        ]
    # a model matches if its name equals the config, or shares the base before ':'
    base = DEFAULT_MODEL.split(":")[0]
    have = any(n == DEFAULT_MODEL or n.split(":")[0] == base for n in names)
    return [
        Check("Ollama server", True, f"up at {OLLAMA_URL}"),
        Check(f"Model '{DEFAULT_MODEL}'", have,
              "available" if have else f"not pulled (have: {', '.join(names) or 'none'})",
              fix=f"ollama pull {DEFAULT_MODEL}   (or set PRAXIS_MODEL to one you have)"),
    ]


def run_checks():
    checks = check_ollama()
    checks += [
        _dep("fastapi"), _dep("uvicorn"), _dep("httpx"), _dep("multipart", "python-multipart"),
        _dep("pypdf", note="document (.pdf) ingest"),
        _dep("docx", "python-docx", note="document (.docx) ingest"),
        _dep("rapidocr_onnxruntime", "rapidocr-onnxruntime", required=False,
             note="image (.png/.jpg) OCR ingest"),
        _dep("whisperx", required=False, note="audio (.mp3/.wav) ingest"),
    ]
    return checks


def format_report(checks):
    lines, ok_required = [], True
    for c in checks:
        mark = "OK " if c.ok else ("XX " if c.required else "-- ")
        lines.append(f"  [{mark}] {c.name}: {c.detail}")
        if not c.ok:
            if c.required:
                ok_required = False
            if c.fix:
                lines.append(f"         fix: {c.fix}")
    return "\n".join(lines), ok_required


def main():
    checks = run_checks()
    report, ready = format_report(checks)
    print("Praxis preflight:\n" + report)
    if ready:
        print("\nReady. Start the app with:  python -m praxis.serve")
    else:
        print("\nNot ready — fix the [XX] items above (the [--] ones are optional ingest formats).")
    raise SystemExit(0 if ready else 1)


if __name__ == "__main__":
    main()
