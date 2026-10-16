"""Read every document's text once, at each rung of the reading ladder, for
training and checking L2 (walkthrough step 3, DECISIONS D23).

Per document (per segment inside a bundle) it keeps:
- native: trusted text from digital pages, DOCX, XLSX, PPTX, TXT, email (free, D22)
- sel:    rung 2, the selective read of the first informative scanned page
- full1:  rung 3, a full read of that page
- more:   rung 4, full reads of the next informative page and the last page
plus the CPU seconds each read took, so the bench can price them.

A document is read by OCR only if its first page has no trusted text. OCR is
the slow part (about 0.6 s per selective read, 3 s per full read on one core),
so this runs on a process pool, renders only the pages it reads, does dev-test
and calibration first, and skips rung 4 for training documents (it adds little
there). It resumes where a stopped run left off.

Writes data/<run>/text.jsonl. Run: python -m scripts.extract_text [sample]
"""
from __future__ import annotations

import csv
import json
import sys
import time
from multiprocessing import Pool

from common.config import DATA_DIR
from pipeline.l2_text.ocr import full_read, is_blank, page_image, selective_read
from pipeline.l0_open.metadata import open_file

WORKERS = 6


def _units(lab: dict, n_pages: int) -> list[tuple[str, str, int, int]]:
    """(unit id, class, first page, last page), 0-based inclusive."""
    if lab["segments"]:
        return [(f"{lab['key']}#{j}", s["class"], s["start"] - 1, s["end"] - 1) for j, s in enumerate(json.loads(lab["segments"]))]
    return [(lab["key"], lab["class"], 0, max(n_pages - 1, 0))]


def _read(job: tuple) -> list[dict]:
    lab, path = job
    r = open_file(lab["key"], path.read_bytes(), "", {})
    out = []
    for uid, cls, a, b in _units(lab, len(r.pages)):
        pages = r.pages[a:b + 1]
        row = dict(unit=uid, key=lab["key"], cls=cls, subtype=lab["subtype"], fmt=lab["fmt"], split=lab["split"],
                   variant=lab["variant"], route=r.route, n_pages=len(pages), native="", sel="", full1="", more="",
                   sel_s=0.0, full1_s=0.0, more_s=0.0, lines=0)
        if not pages:  # text files with no page objects
            row["native"] = r.text
            out.append(row)
            continue
        row["native"] = "\n".join(p.text for p in pages if p.kind == "digital")
        if pages[0].kind == "digital" or r.data is None:
            out.append(row)
            continue
        scanned = [p.index for p in pages if p.kind != "digital"]
        imgs = {}

        def informative(order):  # render pages one at a time, only until a non-blank one is found
            for i in order:
                imgs[i] = imgs.get(i) or page_image(r.data, i)
                if not is_blank(imgs[i]):
                    return i
            return None

        first = informative(scanned)
        if first is None:
            out.append(row)
            continue
        s, f = selective_read(imgs[first]), full_read(imgs[first])
        row.update(sel=s.text, full1=f.text, sel_s=s.seconds, full1_s=f.seconds, lines=f.lines_found)
        later = [i for i in scanned if i > first]
        nxt = informative(later) if lab["split"] != "train" else None
        last = informative(later[::-1]) if nxt is not None else None
        extra = sorted({i for i in (nxt, last) if i is not None})
        if extra:
            reads = [full_read(imgs[i]) for i in extra]
            row.update(more="\n".join(x.text for x in reads), more_s=sum(x.seconds for x in reads))
        out.append(row)
    return out


def main(run: str = "sample") -> None:
    if run.startswith("lockbox"):
        sys.exit("refusing: lockboxes are opened once, by the final run")
    root = DATA_DIR / run
    labs = [lab for lab in csv.DictReader(open(root / "labels.csv")) if not lab["duplicate_of"]]
    have = {}
    if (root / "text.jsonl").exists():
        for line in open(root / "text.jsonl"):
            k = json.loads(line)["key"]
            have[k] = have.get(k, 0) + 1
    expected = {lab["key"]: len(json.loads(lab["segments"])) if lab["segments"] else 1 for lab in labs}
    done_keys = {k for k, n in have.items() if n == expected.get(k)}
    if len(done_keys) < len(have):  # a file stopped half-way: drop its rows and redo it
        keep = [line for line in open(root / "text.jsonl") if json.loads(line)["key"] in done_keys]
        open(root / "text.jsonl", "w").writelines(keep)
    order = {"dev_test": 0, "calib": 1, "train": 2}
    jobs = [(lab, root / "files" / lab["key"]) for lab in sorted(labs, key=lambda x: order[x["split"]]) if lab["key"] not in done_keys]
    print(f"{len(done_keys)} files already read, {len(jobs)} to go", flush=True)
    t0, done = time.time(), 0
    with Pool(WORKERS) as pool, open(root / "text.jsonl", "a") as f:
        for rows in pool.imap_unordered(_read, jobs, chunksize=4):
            for row in rows:
                f.write(json.dumps(row) + "\n")
            done += 1
            f.flush()
            if done % 250 == 0:
                print(f"  {done}/{len(jobs)} files, {time.time() - t0:.0f}s", flush=True)
    print(f"wrote {root / 'text.jsonl'} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
