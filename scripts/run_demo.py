"""Launch the SIIM demonstrator.

Run:  python scripts/run_demo.py

One command, no environment variables, no build step. It puts ``src/`` on the
path itself, so the demo cannot fail on a forgotten ``PYTHONPATH`` — which is
exactly the kind of thing that goes wrong five minutes before a presentation.

Before serving, it **checks the files the real-data cases need and prints what
it finds**. A missing artefact is a thing to discover now, in the room, with
the projector still off — not when a judge is looking at the screen. The server
still starts either way: the synthetic cases are self-contained, and the
real-data cases return a 503 naming the missing file rather than substituting
anything.

**No network access is required.** Every real-data number is read from a
recorded artefact under ``experiments/``; every image is a local PNG.
"""

from __future__ import annotations

import argparse
import socket
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: How many consecutive ports to try after the requested one. A demo machine
#: very often already has something on 8000, and the failure mode that costs a
#: presentation is not "the port was busy" -- it is printing a URL and *then*
#: failing to bind, so the audience is looking at a dead link.
PORT_SEARCH_SPAN = 20


def port_is_free(host: str, port: int) -> bool:
    """True if a server can bind ``(host, port)`` right now.

    Binding and closing is the only reliable test: asking the OS for a list of
    listeners races with anything else starting up, and a connect() probe
    cannot distinguish "nothing is listening" from "something is listening but
    refusing us".
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def choose_port(host: str, preferred: int, span: int = PORT_SEARCH_SPAN
                ) -> tuple[int, bool]:
    """``(port, moved)`` -- the first free port at or after ``preferred``.

    ``moved`` says whether the caller must tell the user the port changed. If
    every port in the window is taken the preferred one is returned with
    ``moved=False``, so the caller still attempts the bind and surfaces the
    real OS error rather than this module inventing one.
    """
    for offset in range(max(1, span)):
        candidate = preferred + offset
        if candidate > 65535:
            break
        if port_is_free(host, candidate):
            return candidate, offset != 0
    return preferred, False


def _ascii_safe_stdout() -> None:
    """Make the pre-flight readable on a legacy Windows console.

    The launcher's first screen is the first thing a judge sees. On a cp1252
    console every em-dash in it renders as a replacement character, which looks
    like a broken program before the demo has even started.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - platform detail
                pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true",
                    help="open the page in a browser once the server is up")
    ap.add_argument("--strict-port", action="store_true",
                    help="fail if --port is taken instead of moving to the "
                         "next free one")
    ap.add_argument("--reload", action="store_true",
                    help="auto-reload on edit. For development, NOT for the "
                         "presentation - a reload mid-demo is a blank screen")
    args = ap.parse_args()

    _ascii_safe_stdout()
    from siim.demo.evidence import real_data_status

    print("== SIIM demonstrator ==\n")
    st = real_data_status()
    if st["available"]:
        print(f"REAL DATA    : available - {len(st['required_files'])} recorded "
              "artefacts on disk, no network needed")
    else:
        print("REAL DATA    : UNAVAILABLE. The real-data cases will return 503, "
              "naming the file, rather than showing anything else.")
        for m in st["missing"]:
            print(f"   missing: {m}")
        print("   fix: re-run REAL-DATA-04, then "
              "python scripts/build_demo_assets.py")
    print("SYNTHETIC    : available - generated live in each request")
    print("CHANDRAYAAN-2: NOT AVAILABLE. No multi-modal claim is supported.")
    print("NETWORK      : not used. Every real number is read from "
          "experiments/; every image is a local PNG.\n")

    port = args.port
    if not args.strict_port:
        port, moved = choose_port(args.host, args.port)
        if moved:
            print(f"NOTE         : port {args.port} is in use; serving on "
                  f"{port} instead.\n")
    elif not port_is_free(args.host, port):
        raise SystemExit(
            f"port {port} is already in use and --strict-port was given. "
            f"Choose another with --port, or drop --strict-port to let the "
            f"launcher move to the next free port.")

    url = f"http://{args.host}:{port}/"
    print(f"open {url}\n")
    if args.open:
        webbrowser.open(url)

    import uvicorn
    uvicorn.run("siim.demo.api:app", host=args.host, port=port,
                reload=args.reload, log_level="warning")


if __name__ == "__main__":
    main()
