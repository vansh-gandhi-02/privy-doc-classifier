"""Unit costs: how many CPU seconds each step takes, measured on one core.

Measured with the process clock, one read at a time, so each read has a core to itself:
- selective read and full read: 150 random scanned pages of the dev sample
- page-number read (the splitter's top and bottom lines, D30): 60 scanned pages
- L1: render, readable signals and DiT on CPU, 200 random pages
- L0: from data/sample/l0.jsonl (scripts/run_l0.py)

Writes data/sample/timing_samples.json (every measurement) and data/bench.json
(the means, plus the fixed per-page costs scaled to 5M documents, which the
controller demo and the cost model read). Measuring takes about 15 minutes; by
default the saved samples are reused.

Assumed page counts for 5M documents (DECISIONS D21, D30): 3 pages per PDF, 2.5 per
TIFF, 1 per image; costs/precision.py shows how the total moves if that is wrong.

Run: python -m costs.timing [--remeasure]
"""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
import time

from common.config import DATA_DIR, load
from pipeline.l0_open.metadata import open_file
from pipeline.l1_layout.layout import Embedder, render_pages, signals
from pipeline.l2_text import ocr

N_OCR, N_CUE, N_L1 = 150, 60, 200
INR_PER_CORE_S = load("brief")["rates_inr"]["cpu_instance_hour"] / load("brief")["cpu_instance_vcpus"] / 3600
PAGES_PER_PDF = 3.0


def pages(n: float, per_pdf: float = PAGES_PER_PDF) -> tuple[float, float, float]:
    """All PDF and image pages; scanned pages; scanned pages inside multi-page files
    (scanned PDFs and TIFFs, which get the splitter's page-number read)."""
    return (n * (0.45 * per_pdf + 0.24 + 0.10 * 2.5), n * (0.183 * per_pdf + 0.24 + 0.10 * 2.5 + 0.018),
            n * (0.183 * per_pdf + 0.10 * 2.5))


def measure_page_cues() -> list[float]:
    """The splitter's page-number read (top and bottom lines, D30) on scanned PDF pages."""
    root = DATA_DIR / "sample"
    labels = [r for r in csv.DictReader(open(root / "labels.csv"))
              if r["modality"] == "scan" and r["fmt"] == "PDF" and r["subtype"] != "bundle" and not r["duplicate_of"]]
    out = []
    for r in random.Random(30).sample(labels, N_CUE):
        f = open_file(r["key"], (root / "files" / r["key"]).read_bytes(), "", {})
        out.append(ocr.page_cue_read(ocr.page_image(f.data, 0)).seconds)
    return out


def measure() -> dict:
    root = DATA_DIR / "sample"
    labels = list(csv.DictReader(open(root / "labels.csv")))
    rng = random.Random(2024)
    scans = [r for r in labels if r["modality"] in ("scan", "photo") and r["subtype"] != "bundle" and not r["duplicate_of"]]
    l1_docs = [r for r in labels if r["fmt"] in ("PDF", "JPG", "PNG", "TIFF") and r["subtype"] != "bundle" and not r["duplicate_of"]]

    def first_page(r):
        f = open_file(r["key"], (root / "files" / r["key"]).read_bytes(), "", {})
        return f, ocr.page_image(f.data, 0)

    out = {"selective": [], "full": [], "page_cue": measure_page_cues(), "l1_render_signals": [], "dit": []}
    for r in rng.sample(scans, N_OCR):
        _, img = first_page(r)
        out["selective"].append(ocr.selective_read(img).seconds)
        out["full"].append(ocr.full_read(img).seconds)
    thumbs = []
    for r in rng.sample(l1_docs, N_L1):
        f = open_file(r["key"], (root / "files" / r["key"]).read_bytes(), "", {})
        c0 = time.process_time()
        img = render_pages(f.data, f.true_type, 1)[0]
        signals(img, f.pages[0].width if f.pages else 0, f.pages[0].height if f.pages else 0)
        out["l1_render_signals"].append(time.process_time() - c0)
        thumbs.append(img)
    emb = Embedder(device="cpu")
    emb(thumbs[:8])
    for i in range(0, len(thumbs), 20):
        c0 = time.process_time()
        emb(thumbs[i:i + 20])
        out["dit"].append((time.process_time() - c0) / len(thumbs[i:i + 20]))
    return out


def main(*args: str) -> None:
    root = DATA_DIR / "sample"
    path = root / "timing_samples.json"
    samples = measure() if "--remeasure" in args or not path.exists() else json.load(open(path))
    if "page_cue" not in samples:   # older sample files predate the page-number read
        samples["page_cue"] = measure_page_cues()
    json.dump(samples, open(path, "w"))
    l0_path = root / "l0.jsonl"
    old = json.load(open(DATA_DIR / "bench.json")) if (DATA_DIR / "bench.json").exists() else {}
    l0 = statistics.mean(json.loads(line)["seconds"] for line in open(l0_path)) if l0_path.exists() else old.get("l0_s_per_file", 0.0025)
    m = {k: statistics.mean(v) for k, v in samples.items()}
    bench = {"l0_s_per_file": l0, "l1_s_per_page": m["l1_render_signals"] + m["dit"], "dit_s_per_page": m["dit"],
             "ocr_selective_s": m["selective"], "ocr_full_s": m["full"], "ocr_page_cue_s": m["page_cue"]}
    n = load("brief")["n_documents"]
    all_p, scanned, multi = pages(n)
    bench["inr"] = {  # fixed per-page costs at 5M, on this Mac (the cloud slowdown is applied where they are used)
        "L0 open every file": n * l0 * INR_PER_CORE_S,
        "L1 every PDF and image page": all_p * bench["l1_s_per_page"] * INR_PER_CORE_S,
        "OCR selective read, every scanned page (D21)": scanned * bench["ocr_selective_s"] * INR_PER_CORE_S,
        "OCR page-number read, scanned pages of multi-page files (D30)": multi * bench["ocr_page_cue_s"] * INR_PER_CORE_S,
    }
    json.dump(bench, open(DATA_DIR / "bench.json", "w"), indent=1)
    print("CPU seconds on one core (mean of the samples):")
    for k, v in bench.items():
        if k != "inr":
            print(f"  {k:22} {v:.3f}")
    print(f"fixed per-page costs at 5M on this Mac: Rs {sum(bench['inr'].values()):,.0f} "
          f"({all_p / 1e6:.1f}M pages, {scanned / 1e6:.1f}M scanned, {multi / 1e6:.1f}M in multi-page scanned files)")


if __name__ == "__main__":
    main(*sys.argv[1:])
