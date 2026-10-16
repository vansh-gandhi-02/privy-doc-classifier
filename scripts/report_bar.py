"""The brief's bar, per class, on every test set.

The bar: macro-F1 >= 0.85 over the 15 classes (each weighted equally) and
recall >= 0.90 on the critical classes (Legal, Property, PoI, PoA, D7).
Documents sent to a person count as errors in the headline (D8).

Reads saved predictions only, so it never re-opens a lockbox:
- dev-test, after L3 (scripts/run_l3_compare.py)
- Lockbox A (sealed, 40% unseen layout) and Lockbox C (fresh, final generator), each run once
- Lockboxes B and D (bank statements from another generator): one class, so
  only recall and the splitter's behaviour mean anything

Run: python -m scripts.report_bar
"""
from __future__ import annotations

import csv
import json

from sklearn.metrics import f1_score, precision_score, recall_score

from common.config import DATA_DIR, class_ids, critical_classes, load

SCORED, CRIT = class_ids(scored_only=True), set(critical_classes())
NAMES = {c: spec["name"] for c, spec in load("classes")["classes"].items()}


def report(name: str, y_true: list[str], y_pred: list[str]) -> dict:
    kw = dict(labels=SCORED, average=None, zero_division=0)
    p, r, f = precision_score(y_true, y_pred, **kw), recall_score(y_true, y_pred, **kw), f1_score(y_true, y_pred, **kw)
    support = {c: sum(t == c for t in y_true) for c in SCORED}
    macro = float(f.mean())
    crit = {c: float(x) for c, x in zip(SCORED, r) if c in CRIT}
    ok = macro >= 0.85 and min(crit.values()) >= 0.90
    print(f"\n{name}  (n={len(y_true)})")
    print(f"  macro-F1 {macro:.3f} (bar 0.85) | lowest critical recall {min(crit.values()):.3f} (bar 0.90) | {'PASSES' if ok else 'FAILS'}")
    print(f"  {'class':40} {'precision':>9} {'recall':>7} {'F1':>6} {'n':>5}")
    for c, pc, rc, fc in zip(SCORED, p, r, f):
        print(f"  {NAMES[c] + (' *' if c in CRIT else ''):40} {pc:9.3f} {rc:7.3f} {fc:6.3f} {support[c]:5d}")
    return {"n": len(y_true), "macro_f1": macro, "critical_recall": crit, "passes": ok,
            "per_class": {c: {"precision": float(pc), "recall": float(rc), "f1": float(fc), "n": support[c]}
                          for c, pc, rc, fc in zip(SCORED, p, r, f)}}


def main() -> None:
    out = {}
    dev = DATA_DIR / "sample" / "final_dev_predictions.csv"
    if dev.exists():
        rows = list(csv.DictReader(open(dev)))
        out["dev_test"] = report("Dev-test, after L3 (human review counted as errors)", [r["true"] for r in rows], [r["pred"] for r in rows])
    for box, title in (("lockbox_a", "Lockbox A: sealed, run once, 40% in a layout never seen in training"),
                       ("lockbox_c", "Lockbox C: fresh from the final generator, built after everything was frozen, run once")):
        path = DATA_DIR / box / "final_predictions.csv"
        if path.exists():
            rows = list(csv.DictReader(open(path)))
            out[box] = report(title, [r["true"] for r in rows], [r["pred"] for r in rows])
    print("\n* critical class")
    for box, title in (("lockbox_b", "Lockbox B: 120 AgamiAI statements, layout-only splitter"),
                       ("lockbox_d", "Lockbox D: 120 fresh AgamiAI statements, with page numbers (D30)")):
        path = DATA_DIR / box / "final_predictions.csv"
        if path.exists():
            rows = list(csv.DictReader(open(path)))
            m = json.load(open(DATA_DIR / box / "final_metrics.json"))
            right = sum(r["pred"] == "bank_statement" for r in rows)
            extra = (f"; single documents kept whole {m['singles_kept_whole']}; first document of each file right {m['first_document_right']}"
                     if "singles_kept_whole" in m else "")
            print(f"\n{title}: {len(rows)} predicted documents from 120 files; bank-statement recall {right / len(rows):.3f}{extra}")
            out[box] = {"pieces": len(rows), "recall": right / len(rows), **{k: m[k] for k in ("singles_kept_whole", "first_document_right") if k in m}}
    json.dump(out, open(DATA_DIR / "sample" / "bar_report.json", "w"), indent=1)


if __name__ == "__main__":
    main()
