"""Run everything in one go.

    python -m scripts.run_all            quick: from the cached artifacts (about 10-15 min on a laptop)
    python -m scripts.run_all --full     rebuild from scratch: generate, render, OCR (about 2 h on 6 cores)

Both end with the tests, the bar report, the flowchart and the approach note.
The lockboxes are not re-run: each is run once (scripts/run_final.py) and
only its saved results are reported. LLM answers come from the cache; new ones
are made only if the `claude` CLI is installed (subscription), never via an API key.
"""
from __future__ import annotations

import subprocess
import sys
import time

FULL = ["docgen.build_sample", "scripts.run_l0", "scripts.extract_pages", "scripts.train_l1", "scripts.train_bundles",
        "scripts.extract_text"]
QUICK = ["tools.artifacts unpack", "scripts.train_l1", "scripts.train_bundles"]
REST = ["costs.timing", "scripts.train_l2", "scripts.run_l3_compare", "scripts.run_controller_demo",
        "scripts.run_controller_demo 23000", "scripts.trace_document", "costs.precision", "costs.baseline", "scripts.check_masker", "scripts.report_bar",
        "tools.make_flowchart", "tools.make_doc"]


def main(*args: str) -> None:
    steps = (FULL if "--full" in args else QUICK) + REST
    t0 = time.time()
    for i, step in enumerate(steps, 1):
        mod, *rest = step.split()
        print(f"\n=== [{i}/{len(steps)}] python -m {step}", flush=True)
        t = time.time()
        if subprocess.run([sys.executable, "-m", mod, *rest]).returncode != 0:
            sys.exit(f"stopped: {step} failed")
        print(f"=== done in {time.time() - t:.0f}s", flush=True)
    print("\n=== tests", flush=True)
    rc = subprocess.run([sys.executable, "-m", "pytest", "-q"]).returncode
    print(f"\nall steps done in {(time.time() - t0) / 60:.1f} min; tests {'pass' if rc == 0 else 'FAIL'}")
    sys.exit(rc)


if __name__ == "__main__":
    main(*sys.argv[1:])
