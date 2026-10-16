"""The one-time run on Lockbox A (DECISIONS D15): the frozen pipeline, run once,
and the report shows whatever comes out.

Guards:
- the labels file must still match the seal recorded in D15
- a marker file is written before anything is read; a second run is refused
  (pass --resume only to finish a run that was interrupted)
- labels are read only at the end, for scoring. Bundles are split by the
  bundle splitter's own predictions, not by the recorded page ranges.

Steps: page features (DiT) for every file, the bundle splitter on multi-page
files, the reading ladder per predicted document, L1 -> L2 -> address question
(pipeline/run.py), then L3 with the mode chosen on the dev sample, then L4.

Lockbox B (D27) is 120 AgamiAI statements, all bank statements, made by a
different generator than ours: it scores recall on one class from outside.

Run: python -m scripts.run_final [lockbox_b] --prepare   (page features and reading only, no models beyond L1)
     python -m scripts.run_final [lockbox_b] --resume    (everything else, once L2 and L3 are final)
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool

import joblib
import numpy as np

from common.config import DATA_DIR, bucket_of, class_ids, critical_classes, load, model_merge
from evaluation.metrics import ABSTAIN, meets_bar
from pipeline.l1_layout.bundles import file_cue_texts
from pipeline.run import llm_text, run_to_l2
from pipeline.l3_llm.llm import LLMSensor, call, candidates
from scripts import extract_pages
from scripts.extract_text import _read
from scripts.run_l3_compare import update

SEALS = {  # SHA-256 of labels.csv, recorded when each lockbox was built (D15, D27)
    "lockbox_a": "bdf42054e6ed73462149bc7f1d9753dd7c087fe46088138f7dbb817951f33d4f",
    "lockbox_b": "fa6ae7f7067e152dd4b190ad3cc6ef5e44d18c40afa1bb87f4f24c0999eb5289",
    "lockbox_c": "c83a4cc095cdabd86230e06cc072407528092e303c9b093bbccea5c0fe904183",  # D29
    "lockbox_d": "d674d69853b77867174c24fbb134cd6a523761de45e2fae72f1b687f2aaece52",  # D30: 120 fresh AgamiAI statements
}
INR_PER_CORE_S = 32 / 8 / 3600
HUMAN_INR = load("budget")["human_review_inr_per_doc"]


def main(*args: str) -> None:
    RUN = next((a for a in args if a in SEALS), "lockbox_a")
    SEAL = SEALS[RUN]
    root = DATA_DIR / RUN
    resume = "--resume" in args or "--prepare" in args
    digest = hashlib.sha256((root / "labels.csv").read_bytes()).hexdigest()
    if digest != SEAL:
        sys.exit(f"refusing: labels.csv no longer matches the D15 seal ({digest[:12]}...)")
    marker = root / ".opened"
    if marker.exists() and not resume:
        sys.exit(f"refusing: {RUN} was already opened at {marker.read_text().strip()}")
    if not marker.exists():
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"seal ok ({SEAL[:12]}...); opened {marker.read_text().strip()}")

    # 1. Page features for every file (same code as the dev sample).
    if not (root / "pages.npz").exists():
        extract_pages.main(RUN, final=True)
    pages = np.load(root / "pages.npz")
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    splitter = joblib.load(DATA_DIR / "models" / "bundles.joblib")
    by_file = defaultdict(list)
    for i, k in enumerate(pages["key"]):
        by_file[k].append(i)
    page_probs = l1.proba(pages["feats"])
    meta = [(k, float(s[0]), float(s[1]), src) for k, s, src in zip(pages["kind"], pages["size"], pages["source"])]

    # 2. Predicted documents per file: the splitter on multi-page files, one document otherwise.
    labs = list(csv.DictReader(open(root / "labels.csv")))
    # Exact duplicates are found the way L0 finds them, by checksum (the label file is not used);
    # a duplicate copies its original's predictions and is scored like any other file.
    first_of, dup_of = {}, {}
    for m in csv.DictReader(open(root / "manifest.csv")):
        if m["checksum"] in first_of:
            dup_of[m["key"]] = first_of[m["checksum"]]
        else:
            first_of[m["checksum"]] = m["key"]
    jobs = []
    pred_segments = {}
    multi = [lab["key"] for lab in labs if lab["key"] not in dup_of and len(by_file.get(lab["key"], [])) > 1]
    with Pool(6) as pool:  # page numbers on every page of multi-page files (D30)
        cue = {Path(path).relative_to(root / "files").as_posix(): texts
               for path, texts, _ in pool.map(file_cue_texts, [str(root / "files" / k) for k in multi])}
    for lab in labs:
        if lab["key"] in dup_of:
            continue
        idx = sorted(by_file.get(lab["key"], []), key=lambda i: pages["page"][i])
        segs = (splitter.segments(pages["feats"][idx], page_probs[idx], [meta[i] for i in idx], cue.get(lab["key"]))
                if len(idx) > 1 else [(0, max(len(idx), 1) - 1)])
        pred_segments[lab["key"]] = segs
        blind = {**lab, "class": "?", "subtype": "?", "split": RUN,
                 "segments": json.dumps([{"start": s + 1, "end": e + 1, "class": "?"} for s, e in segs]) if len(segs) > 1 else ""}
        jobs.append((blind, root / "files" / lab["key"]))

    # 3. Reading ladder text per predicted document.
    text_path = root / "text.jsonl"
    if not text_path.exists():
        t0 = time.time()
        with Pool(6) as pool, open(text_path, "w") as f:
            for i, rows in enumerate(pool.imap_unordered(_read, jobs, chunksize=4), 1):
                for row in rows:
                    f.write(json.dumps(row) + "\n")
                if i % 200 == 0:
                    print(f"  read {i}/{len(jobs)} files, {time.time() - t0:.0f}s", flush=True)
    units = [json.loads(line) for line in open(text_path)]
    if "--prepare" in args:
        print(f"prepared {len(units)} documents; finish with --resume once L2 and L3 are final")
        return

    # 4. L1 -> L2 -> address question.
    model = joblib.load(DATA_DIR / "models" / "l2.joblib")
    check = joblib.load(DATA_DIR / "models" / "address.joblib")
    buckets, merged = bucket_of(), tuple(model_merge())
    row_of = {(k, int(p)): i for i, (k, p) in enumerate(zip(pages["key"], pages["page"]))}
    records = []
    for u in units:
        start = 0
        if "#" in u["unit"]:
            key, j = u["unit"].split("#")
            start = pred_segments[key][int(j)][0]
        r = row_of.get((u["key"], start))
        rec = run_to_l2(u, l1.likelihood(pages["feats"][[r]])[0] if r is not None else None, model, check, buckets, merged)
        rec["key"], rec["start"] = u["key"], start
        records.append(rec)

    # 5. L3 with the mode chosen on the dev sample, then L4.
    l3m = json.load(open(DATA_DIR / "sample" / "l3_metrics.json"))
    mode = l3m["pick"]
    s = l3m["modes"][mode]["sensor"]
    sensor = LLMSensor(s["acc"], s["none_in"], s["none_out"])
    text_of = {u["unit"]: u for u in units}
    to_l3 = [r for r in records if r["pred"] == ABSTAIN]

    def ask(rec):
        probs = json.loads(rec["probs"])
        cands = candidates(probs)
        c = call(llm_text(text_of[rec["unit"]]), cands, mode)
        post = update(probs, sensor.likelihood(c.answer, cands, list(probs)))
        top = max(post, key=post.get)
        return rec["unit"], (top if post[top] >= 0.95 else ABSTAIN), c

    llm_inr = 0.0
    with ThreadPoolExecutor(4) as pool:
        for unit, label, c in pool.map(ask, to_l3):
            rec = next(r for r in records if r["unit"] == unit)
            rec["pred"], rec["stop"], llm_inr = label, ("L3" if label != ABSTAIN else "L4"), llm_inr + c.inr

    # 6. Scoring: labels are read only now. Each predicted document is scored against
    # the true document its first page belongs to; a true document with no predicted
    # document starting on its first page counts as missed.
    truth = {lab["key"]: lab for lab in labs}
    rows = []
    starts_hit = set()
    for rec in records:
        lab = truth[rec["key"]]
        segs = json.loads(lab["segments"]) if lab["segments"] else [{"start": 1, "end": max(int(lab["pages"] or 1), 1), "class": lab["class"]}]
        seg = next((sg for sg in segs if sg["start"] - 1 <= rec["start"] <= sg["end"] - 1), segs[0])
        starts_hit.add((rec["key"], seg["start"]))
        rows.append((seg["class"], rec["pred"], lab["variant"]))
        for dup, orig in dup_of.items():
            if orig == rec["key"]:
                rows.append((seg["class"], rec["pred"], truth[dup]["variant"]))  # an exact copy has the same truth
    missed = 0
    for lab in labs:
        if lab["key"] in dup_of or not lab["segments"]:
            continue
        for sg in json.loads(lab["segments"]):
            if (lab["key"], sg["start"]) not in starts_hit:
                rows.append((sg["class"], "MISSED_SPLIT", lab["variant"]))
                missed += 1
    y_true, y_pred = [t for t, _, _ in rows], [p for _, p, _ in rows]
    bar = meets_bar(y_true, y_pred, class_ids(scored_only=True), critical_classes())
    stops = Counter(r["stop"] for r in records)
    reads_inr = sum((r["full1"] * r["full1_s"] + r["more"] * r["more_s"] + r["sel"] * r["sel_s"]) for r in records) * INR_PER_CORE_S
    n_l4 = sum(r["pred"] == ABSTAIN for r in records)
    unseen = [(t, p) for t, p, v in rows if v == "3"]
    print(f"\n{RUN}: {len(records)} predicted documents from {len(jobs)} files (+{len(dup_of)} exact duplicates, which copy a label); "
          f"{missed} true documents missed by the splitter")
    print(f"stops: {dict(stops)}")
    singles = [lab["key"] for lab in labs if lab["key"] not in dup_of and not lab["segments"]]
    pieces = Counter(r["key"] for r in records)
    kept_whole = sum(pieces[k] == 1 for k in singles)
    firsts = [r for r in records if r["start"] == 0]
    first_right = sum(bool(r["pred"] == truth[r["key"]]["class"] or
                           (truth[r["key"]]["segments"] and r["pred"] == json.loads(truth[r["key"]]["segments"])[0]["class"]))
                      for r in firsts)
    print(f"single documents kept whole by the splitter: {kept_whole}/{len(singles)}; first document of each file right: {first_right}/{len(firsts)}")
    print(f"macro-F1: {bar['macro_f1_abstain_as_error']:.3f} (L4 counted as errors), {bar['macro_f1_abstain_excluded']:.3f} (L4 left out)")
    print("critical recall (L4 counted as misses): " + ", ".join(f"{c} {v:.3f}" for c, v in bar["critical_recall"].items()))
    print(f"passes the brief's bar: {bar['passes']}")
    print(f"unseen layout (variant 3): accuracy {np.mean([t == p for t, p in unseen]):.3f} on {len(unseen)}; "
          f"seen layouts: {np.mean([t == p for t, p, v in rows if v != '3']):.3f}")
    print(f"LLM: {len(to_l3)} calls, Rs {llm_inr:.2f}; humans: {n_l4} documents; extra reads Rs {reads_inr:.2f} (this Mac, 6 workers)")
    json.dump({"n_records": len(records), "missed_splits": missed, "stops": stops, **bar,
               "singles_kept_whole": f"{kept_whole}/{len(singles)}", "first_document_right": f"{first_right}/{len(firsts)}",
               "pieces_per_file": len(records) / max(len(jobs), 1),
               "unseen_accuracy": float(np.mean([t == p for t, p in unseen])), "llm_calls": len(to_l3), "llm_inr": llm_inr,
               "l4_docs": n_l4, "mode": mode}, open(root / "final_metrics.json", "w"), indent=1, default=float)
    with open(root / "final_predictions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["true", "pred", "variant"])
        w.writerows(rows)


if __name__ == "__main__":
    main(*sys.argv[1:])
