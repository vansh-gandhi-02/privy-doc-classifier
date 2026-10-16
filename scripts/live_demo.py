"""A small live run, end to end, on freshly generated documents.

For the Colab notebook: proves the pipeline runs from raw files, not only from
cached results, and measures the reading costs on whatever CPU it runs on (on
Colab, a real cloud vCPU, which settles the "laptop core is not a cloud vCPU"
caveat).

Generates N new documents (a new seed, by the assumed class mix), then for each:
L0 -> L1 (DiT) -> reading ladder -> L2 -> address question. Documents still
unsure would go to L3: the LLM is called only if the `claude` CLI is installed
and logged in (the subscription); otherwise they are listed as "to L3".

Run: python -m scripts.live_demo [n]
"""
from __future__ import annotations

import json
import random
import shutil
import sys
import time
from collections import Counter

import joblib
import numpy as np

from common.config import DATA_DIR, bucket_of, load, model_merge
from docgen.build_sample import make_one
from evaluation.metrics import ABSTAIN
from pipeline.l3_llm.llm import LLMSensor, call, candidates
from pipeline.l4_human.review import HUMAN_REVIEW
from pipeline.run import llm_text, run_to_l2
from scripts.run_l3_compare import update
from pipeline.l0_open.metadata import open_file
from pipeline.l1_layout.layout import Embedder, render_pages, signals
from scripts.extract_text import _read

EXT = {"PDF": "pdf", "JPG": "jpg", "PNG": "png", "TIFF": "tif", "DOCX": "docx", "XLSX": "xlsx", "PPTX": "pptx", "TXT": "txt", "EML": "eml"}


def main(n: str = "40") -> None:
    n = int(n)
    out = DATA_DIR / "demo"
    shutil.rmtree(out, ignore_errors=True)
    (out / "files").mkdir(parents=True)
    rng = random.Random(4242)
    mix = load("class_mix")["classes"]
    classes = list(mix)
    labs = []
    t0 = time.time()
    for i in range(n):
        cls = rng.choices(classes, [mix[c]["share"] for c in classes])[0]
        fmts = {f: w for f, w in mix[cls]["formats"].items() if f in EXT}
        fmt = rng.choices(list(fmts), list(fmts.values()))[0]
        key = f"demo_{i:03d}.{EXT[fmt]}"
        job = dict(seed=rng.randint(0, 2**31), variant=rng.choice([0, 1, 2, 3]), cls=cls, fmt=fmt, path=str(out / "files" / key),
                   key=key, split="demo", last_modified="")
        row = make_one(job)
        labs.append({**row, "class": row["cls"], "duplicate_of": ""})
    print(f"generated {n} documents in {time.time() - t0:.0f}s")

    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    model = joblib.load(DATA_DIR / "models" / "l2.joblib")
    check = joblib.load(DATA_DIR / "models" / "address.joblib")
    embed = Embedder()
    buckets, merged = bucket_of(), tuple(model_merge())
    has_claude = shutil.which("claude") is not None
    l3m = json.load(open(DATA_DIR / "sample" / "l3_metrics.json"))
    sm = l3m["modes"][l3m["pick"]]["sensor"]
    sensor = LLMSensor(sm["acc"], sm["none_in"], sm["none_out"])
    records, l1_s, reads = [], [], Counter()
    for lab in labs:
        path = out / "files" / lab["key"]
        r = open_file(lab["key"], path.read_bytes(), "", {})
        l1_lik = None
        if r.data is not None and r.pages and (r.data[:4] == b"%PDF" or r.true_type in ("JPG", "PNG", "TIFF") or r.pages[0].kind == "image"):
            t = time.process_time()
            img = render_pages(r.data, r.true_type, max_pages=1)[0]
            p = r.pages[0]
            feats = np.concatenate([embed([img])[0], signals(img, p.width, p.height)])[None]
            l1_lik = l1.likelihood(feats)[0]
            l1_s.append(time.process_time() - t)
        u = _read((lab, path))[0]
        for k in ("sel", "full1", "more"):
            if u[f"{k}_s"]:
                reads[k] += 1
                reads[f"{k}_s"] += u[f"{k}_s"]
        rec = run_to_l2(u, l1_lik, model, check, buckets, merged)
        if rec["pred"] == ABSTAIN:   # L3, the same way as the pipeline: the answer is a measured sensor (D25)
            if has_claude:
                probs = json.loads(rec["probs"])
                cands = candidates(probs)
                c = call(llm_text(u), cands, l3m["pick"])
                post = update(probs, sensor.likelihood(c.answer, cands, list(probs)))
                top = max(post, key=post.get)
                rec["pred"], rec["stop"] = (top, "L3 LLM") if post[top] >= 0.95 else (HUMAN_REVIEW, "L4 human")
            else:
                rec["pred"], rec["stop"] = "NEEDS_LLM", "to L3 (no claude CLI here)"
        records.append(rec)
        print(f"  {lab['key']:16} {lab['fmt']:5} true {rec['cls']:22} pred {rec['pred']:22} stopped at {rec['stop']}")
    settled = [r for r in records if r["pred"] not in (HUMAN_REVIEW, "NEEDS_LLM")]
    acc = np.mean([r["pred"] == r["cls"] for r in settled])
    print(f"\nsettled {len(settled)}/{n}, accuracy of settled {acc:.3f}; by the LLM {sum(r['stop'] == 'L3 LLM' for r in records)}; "
          f"to a person {sum(r['pred'] == HUMAN_REVIEW for r in records)}; waiting for an LLM {sum(r['pred'] == 'NEEDS_LLM' for r in records)}")
    print("timings on this machine (CPU seconds): " + f"L1 {np.mean(l1_s):.2f}/page" +
          "".join(f", {k} read {reads[f'{k}_s'] / reads[k]:.2f}" for k in ("sel", "full1") if reads[k]))


if __name__ == "__main__":
    main(*sys.argv[1:])
