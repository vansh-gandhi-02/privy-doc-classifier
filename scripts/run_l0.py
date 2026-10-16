"""Run L0 over a generated sample, cache the results, and check them against the labels.

Checks (dev sample only; never run on a lockbox before the final run):
- every planted duplicate is caught, and nothing else is flagged
- the true type matches the file's real format
- digital vs scan per document matches how the generator made it
- CPU time per file, by format

Run: python -m scripts.run_l0 [sample]
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict

from common.config import DATA_DIR
from pipeline.l0_open.metadata import open_file

EXPECTED_ROUTE = {"digital": "text", "scan": "image", "photo": "image", "screenshot": "image", "attachment-photo": "image", "attachment-pdf": "text"}


def main(run: str = "sample") -> None:
    if run.startswith("lockbox"):
        sys.exit("refusing: lockboxes are opened once, by the final run")
    root = DATA_DIR / run
    manifest = list(csv.DictReader(open(root / "manifest.csv")))
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    seen, out, secs = {}, [], defaultdict(list)
    for m in manifest:
        r = open_file(m["key"], (root / "files" / m["key"]).read_bytes(), m["checksum"], seen)
        out.append(r)
        secs[labels[m["key"]]["fmt"]].append(r.seconds)
    with open(root / "l0.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps({"key": r.key, "true_type": r.true_type, "fmt": r.fmt, "route": r.route, "duplicate_of": r.duplicate_of,
                                "pages": [{"kind": p.kind, "w": p.width, "h": p.height, "chars": len(p.text), "source": list(p.source)} for p in r.pages],
                                "text_chars": len(r.text), "seconds": r.seconds}) + "\n")

    # A pair counts as caught whichever copy comes first in the listing.
    planted = {frozenset((k, l["duplicate_of"])) for k, l in labels.items() if l["duplicate_of"]}
    found = {frozenset((r.key, r.duplicate_of)) for r in out if r.duplicate_of}
    print(f"duplicate pairs: planted {len(planted)}, caught {len(planted & found)}, false alarms {len(found - planted)}")
    fmt_ok = sum(1 for r in out if not r.duplicate_of and r.fmt == labels[r.key]["fmt"])
    print(f"true type matches format: {fmt_ok}/{sum(1 for r in out if not r.duplicate_of)}")
    route_ok, route_n, confusion = 0, 0, Counter()
    for r in out:
        lab = labels[r.key]
        exp = EXPECTED_ROUTE.get(lab["modality"])
        if r.duplicate_of or exp is None or lab["fmt"] in ("DOCX", "XLSX", "TXT", "PPTX"):
            continue
        route_n += 1
        route_ok += r.route == exp
        confusion[(lab["modality"], r.route)] += 1
    print(f"route matches how the file was made: {route_ok}/{route_n}")
    print("  (modality, route):", dict(confusion))
    print("CPU ms per file, median by format:", {k: round(1000 * statistics.median(v), 1) for k, v in sorted(secs.items())})


if __name__ == "__main__":
    main(*sys.argv[1:])
