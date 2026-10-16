"""Generate a sample: the files, plus the manifest and labels everything else reads.

Two runs:
  python -m docgen.build_sample              dev sample: train / calib / dev_test, layout variants 0-2
  python -m docgen.build_sample --lockbox    Lockbox A: a new seed, includes the unseen variant 3, sealed

Each run writes, under data/<name>/:
  files/<xx>/<key>  the documents
  manifest.csv      key, size_bytes, last_modified, checksum: what the brief's free
                    manifest gives. The pipeline sees only this and the files.
  labels.csv        ground truth, never read by the pipeline: class, subtype, format,
                    modality, layout variant, split, pages, bundle segments, duplicate_of
  contact_sheet.jpg one example page per sub-type, for a human look

Bundles (D21): about 10% of PDFs are merged loan files of 2 to 5 documents, with
true page ranges in labels.csv. Duplicates (D19): 2% exact byte copies.
Lockbox A's labels.csv is hashed into SEAL.txt, so we can show it was not
opened or edited before the final run (D15).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from datetime import datetime, timedelta
from multiprocessing import Pool
from pathlib import Path

from common.config import DATA_DIR, bucket_of, load
from docgen import render
from docgen.layout import A4, Doc, P, Page, style_for
from docgen.plan import plan
from docgen.templates import make

EXT = {"PDF": "pdf", "JPG": "jpg", "TIFF": "tif", "DOCX": "docx", "PNG": "png", "EML": "eml", "XLSX": "xlsx", "TXT": "txt", "PPTX": "pptx", "OTH": "zip"}
# What a merged loan file tends to contain after its first document.
LOAN_FILE = {"proof_of_identity": 3, "proof_of_address": 3, "bank_statement": 3, "salary_slip": 2, "itr": 2, "property_collateral": 1,
             "gst": 1, "audited_financials": 0.5, "company_constitution": 0.5, "legal_contract": 0.5, "class10_marksheet": 0.5, "class12_marksheet": 0.5}
BUNDLE_SHARE = 0.10
DUPLICATE_SHARE = 0.02
RUNS = {
    "sample": dict(seed=7, variants=[0, 1, 2], weights=[1, 1, 1], core=None, min_per_class=None),
    "lockbox_a": dict(seed=90210, variants=[0, 1, 2, 3], weights=[0.2, 0.2, 0.2, 0.4], core=600, min_per_class=40),
    # D29: a smaller fresh lockbox from the fixed generator (D23 option B), new seed, built after everything was frozen
    "lockbox_c": dict(seed=31337, variants=[0, 1, 2, 3], weights=[0.2, 0.2, 0.2, 0.4], core=300, min_per_class=20),
}

_SUBTYPES = load("subtypes")["subtypes"]
_NAMES = {c: s["name"] for c, s in load("classes")["classes"].items()}


def pick_subtype(rng: random.Random, cls: str, fmt: str) -> tuple[str, str]:
    cands = [(s, spec) for s, spec in _SUBTYPES.items() if spec["class"] == cls and fmt in spec["formats"]]
    s, spec = rng.choices(cands, [spec.get("weight", 1) for _, spec in cands])[0]
    return s, spec["formats"][fmt]


def _email_for(rng: random.Random, cls: str) -> Doc:
    name = _NAMES[cls]
    subject = rng.choice([f"{name} - documents for processing", "Please find attached", "Documents as requested", "Fwd: documents", "Re: pending documents"])
    body = rng.choice([f"Dear Sir/Madam,\n\nPlease find attached my {name.lower()} as requested.\n\nRegards",
                       "Dear Sir/Madam,\n\nPlease find the attached document for your records.\n\nThanks and regards",
                       "Hi,\n\nAttaching the document you asked for. Let me know if anything else is needed.\n\nThanks"])
    return Doc(subject, [Page(A4).add(P(36, 40, 523, 200, body, size=9))], "helv")


def _key(run: str, i: int, fmt: str) -> str:
    h = hashlib.sha1(f"{run}-{i}".encode()).hexdigest()[:20]
    return f"{h[:2]}/{h}.{EXT[fmt]}"


def make_one(job: dict) -> dict:
    rng = random.Random(job["seed"])
    st = style_for(rng, job["variant"])
    cls, fmt, path = job["cls"], job["fmt"], Path(job["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "EML" and cls != "other":
        sub_fmt = "PDF" if any(s["class"] == cls and "PDF" in s["formats"] for s in _SUBTYPES.values()) else "JPG"
        subtype, _ = pick_subtype(rng, cls, sub_fmt)
        attachment = render.attachment_bytes(make(subtype, rng, st), rng)
        pages = render.write(_email_for(rng, cls), "EML", "digital", path, rng, attachment=attachment)
        modality = "attachment-" + ("pdf" if attachment[3] == "pdf" else "photo")
    else:
        subtype, modality = pick_subtype(rng, cls, fmt)
        pages = render.write(make(subtype, rng, st), fmt, modality, path, rng)
    return {**_row(job), "subtype": subtype, "modality": modality, "pages": pages, "segments": ""}


def make_bundle(job: dict) -> dict:
    import pymupdf
    rng = random.Random(job["seed"])
    path = Path(job["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    first = rng.choices(["loan_application", "cc_application", None], [5, 2, 3])[0] or rng.choices(list(LOAN_FILE), list(LOAN_FILE.values()))[0]
    classes = [first] + rng.choices(list(LOAN_FILE), list(LOAN_FILE.values()), k=rng.randint(1, 4))
    out, segments, page = pymupdf.open(), [], 0
    for cls in classes:
        st = style_for(rng, rng.choices(job["variants"], job["weights"])[0])
        subtype, modality = pick_subtype(rng, cls, "PDF")
        part = render.pdf_document(make(subtype, rng, st), modality if rng.random() < 0.6 else "scan", rng)
        out.insert_pdf(part)
        segments.append({"start": page + 1, "end": page + len(part), "class": cls, "subtype": subtype})
        page += len(part)
    out.save(path, deflate=True)
    return {**_row(job), "cls": classes[0], "subtype": "bundle", "modality": "bundle", "pages": page, "segments": json.dumps(segments)}


def _row(job: dict) -> dict:
    return {k: job[k] for k in ("key", "cls", "fmt", "variant", "split", "last_modified")}


def build(run: str, workers: int = 6) -> Path:
    cfg = RUNS[run]
    out = DATA_DIR / run
    if (out / ".opened").exists():
        raise SystemExit(f"refusing: {run} has already been opened by a final run and must not be rebuilt")
    if out.exists():
        shutil.rmtree(out)
    files = out / "files"
    files.mkdir(parents=True)
    rng = random.Random(cfg["seed"])
    p = plan(core_size=cfg["core"], min_per_class=cfg["min_per_class"])
    cells = {}
    for part in ("core", "topup"):
        for cell, n in p[part].items():
            cells[cell] = cells.get(cell, 0) + n
    jobs, i = [], 0

    def new_job(**extra) -> dict:
        nonlocal i
        variant = rng.choices(cfg["variants"], cfg["weights"])[0]
        split = run if run.startswith("lockbox") else rng.choices(["train", "calib", "dev_test"], [0.6, 0.2, 0.2])[0]
        stamp = datetime(2019, 1, 1) + timedelta(seconds=rng.randint(0, 7 * 365 * 86400))
        job = dict(seed=rng.randint(0, 2**31), variant=variant, split=split, last_modified=stamp.isoformat(), **extra)
        job["key"] = _key(run, i, job["fmt"])
        job["path"] = str(files / job["key"])
        i += 1
        return job

    for (cls, fmt), n in sorted(cells.items()):
        jobs += [new_job(cls=cls, fmt=fmt) for _ in range(n)]
    n_pdf = sum(n for (_, fmt), n in cells.items() if fmt == "PDF")
    bundles = [new_job(cls="", fmt="PDF", variants=cfg["variants"], weights=cfg["weights"]) for _ in range(round(n_pdf * BUNDLE_SHARE))]

    rows = []
    with Pool(workers) as pool:
        for k, row in enumerate(pool.imap_unordered(make_one, jobs, chunksize=8), start=1):
            rows.append(row)
            if k % 500 == 0:
                print(f"  {k}/{len(jobs)} documents")
        rows += pool.map(make_bundle, bundles, chunksize=4)
    print(f"  {len(rows)} files incl. {len(bundles)} bundles")

    singles = [r for r in rows if r["subtype"] != "bundle"]
    for r in rng.sample(singles, round(len(singles) * DUPLICATE_SHARE)):
        dup = dict(r, key=_key(run, i, r["fmt"]), duplicate_of=r["key"])
        i += 1
        (files / dup["key"]).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(files / r["key"], files / dup["key"])
        rows.append(dup)

    rows.sort(key=lambda r: r["key"])
    buckets = bucket_of()
    with open(out / "manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "size_bytes", "last_modified", "checksum"])
        for r in rows:
            data = (files / r["key"]).read_bytes()
            w.writerow([r["key"], len(data), r["last_modified"], hashlib.sha256(data).hexdigest()])
    fields = ["key", "class", "bucket", "subtype", "fmt", "modality", "variant", "split", "pages", "segments", "duplicate_of"]
    with open(out / "labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for r in rows:
            w.writerow({"key": r["key"], "class": r["cls"], "bucket": buckets[r["cls"]], "subtype": r["subtype"], "fmt": r["fmt"],
                        "modality": r["modality"], "variant": r["variant"], "split": r["split"], "pages": r["pages"],
                        "segments": r.get("segments", ""), "duplicate_of": r.get("duplicate_of", "")})
    if run.startswith("lockbox"):
        digest = hashlib.sha256((out / "labels.csv").read_bytes()).hexdigest()
        (out / "SEAL.txt").write_text(f"labels.csv sha256 {digest}\nsealed {datetime.now().isoformat(timespec='seconds')}\n")
        print(f"  sealed: labels.csv sha256 {digest}")
    contact_sheet(out, rows)
    return out


def contact_sheet(out: Path, rows: list[dict], cell: int = 260) -> None:
    import pymupdf
    from PIL import Image, ImageDraw
    seen, picks = set(), []
    for r in rows:
        if r["fmt"] in ("PDF", "JPG", "PNG", "TIFF") and r["subtype"] not in seen and not r.get("duplicate_of"):
            seen.add(r["subtype"])
            picks.append(r)
    cols = 8
    sheet = Image.new("RGB", (cols * cell, ((len(picks) + cols - 1) // cols) * (cell + 16)), (225, 225, 225))
    draw = ImageDraw.Draw(sheet)
    for k, r in enumerate(picks):
        path = out / "files" / r["key"]
        if r["fmt"] == "PDF":
            pix = pymupdf.open(path)[0].get_pixmap(dpi=40)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        else:
            im = Image.open(path).convert("RGB")
        im.thumbnail((cell - 6, cell - 6))
        x, y = (k % cols) * cell, (k // cols) * (cell + 16)
        sheet.paste(im, (x + 3, y + 3))
        draw.text((x + 4, y + cell + 1), f"{r['subtype']} {r['fmt']} {r['modality']}"[:42], fill=(0, 0, 0))
    sheet.save(out / "contact_sheet.jpg", "JPEG", quality=80)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lockbox", action="store_true", help="build Lockbox A instead of the dev sample")
    ap.add_argument("--run", choices=list(RUNS), help="build this run (e.g. lockbox_c)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    out = build(args.run or ("lockbox_a" if args.lockbox else "sample"), args.workers)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
