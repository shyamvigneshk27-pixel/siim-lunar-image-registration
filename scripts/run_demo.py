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
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true",
                    help="open the page in a browser once the server is up")
    ap.add_argument("--reload", action="store_true",
                    help="auto-reload on edit. For development, NOT for the "
                         "presentation — a reload mid-demo is a blank screen")
    args = ap.parse_args()

    from siim.demo.evidence import real_data_status

    print("== SIIM demonstrator ==\n")
    st = real_data_status()
    if st["available"]:
        print(f"REAL DATA   : available — {len(st['required_files'])} recorded "
              "artefacts on disk, no network needed")
    else:
        print("REAL DATA   : UNAVAILABLE. The real-data cases will return 503, "
              "naming the file, rather than showing anything else.")
        for m in st["missing"]:
            print(f"   missing: {m}")
        print("   fix: re-run REAL-DATA-04, then "
              "python scripts/build_demo_assets.py")
    print("SYNTHETIC   : available — generated live in each request")
    print("CHANDRAYAAN-2: NOT AVAILABLE. No multi-modal claim is supported.\n")

    url = f"http://{args.host}:{args.port}/"
    print(f"open {url}\n")
    if args.open:
        webbrowser.open(url)

    import uvicorn
    uvicorn.run("siim.demo.api:app", host=args.host, port=args.port,
                reload=args.reload, log_level="warning")


if __name__ == "__main__":
    main()
