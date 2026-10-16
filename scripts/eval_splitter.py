"""Does reading printed page numbers fix the bundle splitter? (D30)

Lockbox B showed the splitter cutting unfamiliar multi-page statements into
pieces. The fix: read the page-number line of every page and let "Page 3"
forbid a cut and "Page 1" force one. This script measures the splitter with
and without that rule on:
- our dev-test multi-page files (bundles must still split exactly; single
  documents must stay whole)
- a dev batch of 80 fresh AgamiAI statements (data/agami_dev; each file is one
  statement, so it should stay whole)
The final check is a single run on the sealed Lockbox D (scripts/run_final.py).

Run: python -m scripts.eval_splitter
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from multiprocessing import Pool

import joblib
import numpy as np

from common.config import DATA_DIR
from pipeline.l1_layout.bundles import page_cue_texts
from pipeline.l0_open.metadata import open_file
from pipeline.l1_layout.layout import Embedder, render_pages, signals


def _texts(path: str):
    data = open(path, "rb").read()
    r = open_file(path, data, "", {})
    texts, secs = page_cue_texts(r)
    return path, texts, secs, [(p.kind, p.width, p.height, str(p.source)) for p in r.pages[:12]]


def dev_sample(model, l1) -> dict:
    root = DATA_DIR / "sample"
    d = np.load(root / "pages.npz")
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    files = defaultdict(list)
    for i, k in enumerate(d["key"]):
        if labels[k]["split"] == "dev_test":
            files[k].append(i)
    multi = {k: sorted(v, key=lambda i: d["page"][i]) for k, v in files.items() if len(v) > 1}
    with Pool(6) as pool:
        texts = {k.replace(str(root / "files") + "/", ""): t for k, t, _, _ in pool.map(_texts, [str(root / "files" / k) for k in multi])}
    probs = l1.proba(d["feats"])
    meta = [(k, float(s[0]), float(s[1]), src) for k, s, src in zip(d["kind"], d["size"], d["source"])]
    out = {}
    for use in (False, True):
        exact = n_b = false_split = n_s = 0
        for k, idx in multi.items():
            segs = model.segments(d["feats"][idx], probs[idx], [meta[i] for i in idx], texts[k] if use else None)
            pred = {s for s, _ in segs}
            true = {j for j, i in enumerate(idx) if d["first"][i]}
            if labels[k]["subtype"] == "bundle":
                n_b += 1
                exact += pred == true
            else:
                n_s += 1
                false_split += len(segs) > 1
        out["with page numbers" if use else "layout only"] = dict(bundles_exact=f"{exact}/{n_b}", singles_split=f"{false_split}/{n_s}")
    return out


def agami(model, l1) -> dict:
    root = DATA_DIR / "agami_dev"
    keys = [r["key"] for r in csv.DictReader(open(root / "labels.csv"))]
    emb = Embedder()
    with Pool(6) as pool:
        texts = {t[0]: t for t in pool.map(_texts, [str(root / "files" / k) for k in keys])}
    out, secs = {}, sum(t[2] for t in texts.values())
    feats = {}
    for k in keys:
        path = str(root / "files" / k)
        r = open_file(k, open(path, "rb").read(), "", {})
        ims = render_pages(r.data, r.true_type, 12)
        sig = np.stack([signals(im, r.pages[i].width, r.pages[i].height) for i, im in enumerate(ims)])
        feats[k] = np.concatenate([emb(ims), sig], axis=1).astype(np.float32)
    for use in (False, True):
        pieces = []
        for k in keys:
            f = feats[k]
            _, t, _, meta = texts[str(root / "files" / k)]
            pieces.append(len(model.segments(f, l1.proba(f), meta[:len(f)], t if use else None)))
        out["with page numbers" if use else "layout only"] = dict(pieces_per_file=round(float(np.mean(pieces)), 2),
                                                                 kept_whole=f"{sum(p == 1 for p in pieces)}/{len(keys)}")
    out["page-number reads, CPU s per scanned page"] = round(secs / max(1, sum(1 for t in texts.values() if t[2] > 0) * 6), 3)
    return out


def main() -> None:
    model = joblib.load(DATA_DIR / "models" / "bundles.joblib")
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    res = {"dev_test (ours)": dev_sample(model, l1), "agami_dev (80 fresh statements)": agami(model, l1)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(DATA_DIR / "sample" / "splitter_eval.json", "w"), indent=1)


if __name__ == "__main__":
    main()
