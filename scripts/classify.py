"""Classify any folder of documents: the whole pipeline, end to end, no labels needed.

    python -m scripts.classify <folder> [--out predictions.csv] [--no-llm]

For every file: L0 (true type, trusted text, exact duplicates by checksum, which
copy the first copy's label), L1 page features (DiT) for every page, the bundle
splitter on multi-page files, the reading ladder per document, L1 -> L2 -> address
question (pipeline/run.py), then L3 through `claude -p` (if the CLI is here and
--no-llm is not set) and L4 for whatever is still unsure.

Writes one row per document found (several per bundled file): file, pages,
label (or "HUMAN_REVIEW"), confidence, the step that settled it, and its
estimated cost on a cloud vCPU (2x this laptop) at the brief's rates.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import joblib
import numpy as np

from common.config import DATA_DIR, bucket_of, load, model_merge
from evaluation.metrics import ABSTAIN
from pipeline.l1_layout.bundles import file_cue_texts
from pipeline.run import llm_text, run_to_l2
from pipeline.l0_open.metadata import open_file
from pipeline.l1_layout.layout import Embedder, render_pages, signals
from pipeline.l3_llm.llm import LLMSensor, call, candidates
from scripts.extract_text import _read
from scripts.run_l3_compare import update

MAX_PAGES = 12
CLOUD, INR_PER_CORE_S = 2.0, 32 / 8 / 3600
HUMAN_INR = load("budget")["human_review_inr_per_doc"]


def main(*args: str) -> None:
    folder = Path(args[0]).expanduser()
    out = Path(args[args.index("--out") + 1]) if "--out" in args else folder.parent / f"{folder.name}_predictions.csv"
    use_llm = "--no-llm" not in args and shutil.which("claude") is not None
    bench = json.load(open(DATA_DIR / "bench.json"))
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    model = joblib.load(DATA_DIR / "models" / "l2.joblib")
    check = joblib.load(DATA_DIR / "models" / "address.joblib")
    splitter = joblib.load(DATA_DIR / "models" / "bundles.joblib")
    l3m = json.load(open(DATA_DIR / "sample" / "l3_metrics.json"))
    mode = l3m["pick"]
    s = l3m["modes"][mode]["sensor"]
    sensor = LLMSensor(s["acc"], s["none_in"], s["none_out"])
    buckets, merged = bucket_of(), tuple(model_merge())
    t0 = time.time()

    # L0 and page images.
    files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.name.startswith("."))
    seen, l0, imgs, dup = {}, {}, {}, {}
    for p in files:
        key = str(p.relative_to(folder))
        data = p.read_bytes()
        r = open_file(key, data, hashlib.sha256(data).hexdigest(), seen)
        if r.duplicate_of:
            dup[key] = r.duplicate_of
            continue
        l0[key] = r
        if r.data is not None and r.pages and (r.data[:4] == b"%PDF" or r.true_type in ("JPG", "PNG", "TIFF") or r.pages[0].kind == "image"):
            imgs[key] = render_pages(r.data, r.true_type, MAX_PAGES)
    print(f"L0: {len(files)} files, {len(dup)} exact duplicates, {len(imgs)} with page images ({time.time() - t0:.0f}s)", flush=True)

    # L1 page features, then the bundle splitter.
    embed = Embedder()
    feats = {}
    for key, ims in imgs.items():
        pages = l0[key].pages
        emb = embed(ims)
        sig = np.stack([signals(im, pages[i].width if i < len(pages) else 0, pages[i].height if i < len(pages) else 0) for i, im in enumerate(ims)])
        feats[key] = np.concatenate([emb, sig], axis=1).astype(np.float32)
    multi = [key for key, f in feats.items() if len(f) > 1]
    with Pool(6) as pool:  # page numbers on every page of multi-page files (D30)
        cue = {Path(path).relative_to(folder).as_posix(): (t, sec) for path, t, sec in pool.map(file_cue_texts, [str(folder / k) for k in multi])}
    segs = {}
    for key in multi:
        f = feats[key]
        meta = [(p.kind, p.width, p.height, str(p.source)) for p in l0[key].pages[:len(f)]]
        segs[key] = splitter.segments(f, l1.proba(f), meta, cue[key][0])
    print(f"L1 + splitter: {sum(len(f) for f in feats.values())} pages, {sum(len(v) > 1 for v in segs.values())} files split ({time.time() - t0:.0f}s)", flush=True)

    # Reading ladder per predicted document (parallel OCR).
    jobs = []
    for key, r in l0.items():
        sg = segs.get(key, [(0, max(len(r.pages), 1) - 1)])
        lab = {"key": key, "class": "?", "subtype": "?", "fmt": r.fmt, "split": "classify", "variant": "",
               "segments": json.dumps([{"start": a + 1, "end": b + 1, "class": "?"} for a, b in sg]) if len(sg) > 1 else ""}
        jobs.append((lab, folder / key))
    with Pool(6) as pool:
        units = [u for rows in pool.imap_unordered(_read, jobs, chunksize=2) for u in rows]
    print(f"reading ladder: {len(units)} documents ({time.time() - t0:.0f}s)", flush=True)

    # L1 -> L2 -> address question -> L3 -> L4.
    rows = []
    for u in sorted(units, key=lambda u: u["unit"]):
        start = segs[u["key"]][int(u["unit"].split("#")[1])][0] if "#" in u["unit"] else 0
        f = feats.get(u["key"])
        l1_lik = l1.likelihood(f[[start]])[0] if f is not None and start < len(f) else None
        rec = run_to_l2(u, l1_lik, model, check, buckets, merged)
        cost = (rec["full1"] + rec["more"] * max(rec["n_more"], 1)) * bench["ocr_full_s"] * INR_PER_CORE_S * CLOUD
        label, conf, step = rec["pred"], rec["conf"], rec["stop"]
        if label == ABSTAIN:
            if use_llm:
                probs = json.loads(rec["probs"])
                cands = candidates(probs)
                c = call(llm_text(u), cands, mode)
                post = update(probs, sensor.likelihood(c.answer, cands, list(probs)))
                top = max(post, key=post.get)
                cost += c.inr
                label, conf, step = (top, post[top], "L3 LLM") if post[top] >= 0.95 else ("HUMAN_REVIEW", post[top], "L4 human")
            else:
                label, step = "NEEDS_LLM", "to L3 (LLM switched off)"
            if label == "HUMAN_REVIEW":
                cost += HUMAN_INR
        pages = "" if "#" not in u["unit"] else "{}-{}".format(*[x + 1 for x in segs[u["key"]][int(u["unit"].split("#")[1])]])
        rows.append(dict(file=u["key"], pages=pages, label=label, confidence=round(conf, 4), step=step, cost_inr=round(cost, 5)))
    for key, orig in dup.items():
        for r in [r for r in rows if r["file"] == orig]:
            rows.append({**r, "file": key, "step": f"duplicate of {orig}", "cost_inr": 0.0})
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    steps = {}
    for r in rows:
        steps[r["step"]] = steps.get(r["step"], 0) + 1
    print(f"\n{len(rows)} documents from {len(files)} files in {time.time() - t0:.0f}s; by step: {steps}")
    print(f"estimated cost {sum(r['cost_inr'] for r in rows):.3f} Rs for reads, LLM and humans "
          f"(plus about {bench['l1_s_per_page'] * CLOUD * INR_PER_CORE_S * 1000:.2f} paise per page for L1); wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
