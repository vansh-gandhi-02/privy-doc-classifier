"""Describe every page once: DiT summary + readable signals, cached for training L1
and the bundle splitter (the "describe each page" job in DECISIONS D20).

Writes data/<run>/pages.npz with, per page: document key, page number, the
features, the page's true class (the segment's class inside a bundle), whether
the page starts a document, page kind, size and scanner fingerprint.

Run: python -m scripts.extract_pages [sample]
"""
from __future__ import annotations

import csv
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

from common.config import DATA_DIR
from pipeline.l0_open.metadata import open_file
from pipeline.l1_layout.layout import Embedder, render_pages, signals

MAX_PAGES = 12


def _render(args):
    key, data, true_type, pages = args
    imgs = render_pages(data, true_type, MAX_PAGES)
    out = []
    for i, img in enumerate(imgs):
        p = pages[i] if i < len(pages) else None
        out.append((key, i, img, signals(img, p.width if p else 0, p.height if p else 0),
                    p.kind if p else "image", (p.width, p.height) if p else img.size, str(p.source) if p else ""))
    return out


def main(run: str = "sample", final: bool = False) -> None:
    if run.startswith("lockbox") and not final:
        sys.exit("refusing: lockboxes are opened once, by the final run (scripts/run_final.py)")
    root = DATA_DIR / run
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    seen, jobs = {}, []
    for m in csv.DictReader(open(root / "manifest.csv")):
        r = open_file(m["key"], (root / "files" / m["key"]).read_bytes(), m["checksum"], seen)
        if r.duplicate_of or not r.pages or r.data is None:
            continue
        if not (r.data[:4] == b"%PDF" or r.true_type in ("JPG", "PNG", "TIFF") or r.pages[0].kind == "image"):
            continue  # DOCX, XLSX, TXT, PPTX, email bodies: no page image, text first (D22)
        jobs.append((r.key, r.data, r.true_type, r.pages))
    t0 = time.time()
    with Pool(6) as pool:
        rendered = [page for doc in pool.imap(_render, jobs, chunksize=8) for page in doc]
    print(f"rendered {len(rendered)} pages from {len(jobs)} documents in {time.time() - t0:.0f}s")
    t0 = time.time()
    emb = Embedder()(([r[2] for r in rendered]))
    print(f"DiT on {len(rendered)} pages in {time.time() - t0:.0f}s on {Embedder.__name__}")

    keys, page_no, cls, first, kind, size, source, split = [], [], [], [], [], [], [], []
    for key, i, _, _, k, sz, src in rendered:
        lab = labels[key]
        c, starts = lab["class"], i == 0
        if lab["segments"]:
            for seg in json.loads(lab["segments"]):
                if seg["start"] - 1 <= i <= seg["end"] - 1:
                    c, starts = seg["class"], i == seg["start"] - 1
        keys.append(key), page_no.append(i), cls.append(c), first.append(starts), kind.append(k)
        size.append(sz), source.append(src), split.append(lab["split"])
    feats = np.concatenate([emb, np.stack([r[3] for r in rendered])], axis=1).astype(np.float32)
    np.savez_compressed(root / "pages.npz", key=np.array(keys), page=np.array(page_no), feats=feats, cls=np.array(cls),
                        first=np.array(first), kind=np.array(kind), size=np.array(size, dtype=np.float32),
                        source=np.array(source), split=np.array(split))
    print(f"wrote {root / 'pages.npz'}: {feats.shape}")


if __name__ == "__main__":
    main(*sys.argv[1:])
