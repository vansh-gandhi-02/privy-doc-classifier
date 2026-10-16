"""L0: open the file. What it really is, which text can be trusted, and where
each document starts from (walkthrough step 1, DECISIONS D19 and D22).

Per file, without OCR and without any model:
- true type from the first bytes, not the extension
- for PDFs, per page: digital (visible text we trust) or scan, page size, and
  the scanner fingerprint of scanned pages (image size, colour, compression);
  these are free boundary cues for bundles (D21)
- free text: digital PDF pages, DOCX, XLSX, PPTX, TXT, email bodies
- emails and ZIPs are unpacked, and the attachment becomes the document (D12)
- exact duplicates by checksum: a later copy just points at the first
- the starting probabilities: the class mix for this format (class_mix.yaml),
  never exactly zero

Route (D22): "text" when trusted text exists and nothing is scanned, "image"
when there is no trusted text, "mixed" for PDFs with both kinds of page.
"""
from __future__ import annotations

import email
import io
import time
import zipfile
from dataclasses import dataclass, field
from email import policy
from functools import lru_cache

import pymupdf
from PIL import Image, ImageSequence

from common.config import load, to_model_dist
from pipeline.l0_open.filetype import MIN_VISIBLE_CHARS, office_kind, pdf_page_kind, sniff

FLOOR = 1e-4
TYPE_TO_FORMAT = {"PDF": "PDF", "JPG": "JPG", "PNG": "PNG", "TIFF": "TIFF", "DOCX": "DOCX", "XLSX": "XLSX", "PPTX": "PPTX",
                  "TXT": "TXT", "EML": "EML", "OLE": "EML", "ZIP": "OTH", "UNKNOWN": "OTH"}


@dataclass
class PageInfo:
    index: int
    kind: str                       # "digital", "scan" or "image"
    width: float
    height: float
    text: str = ""                  # trusted text, digital pages only
    source: tuple = ()              # scanner fingerprint of a scanned page


@dataclass
class L0Result:
    key: str
    true_type: str
    fmt: str                        # format used for the prior (true type, not extension)
    route: str                      # "text", "image" or "mixed"
    pages: list[PageInfo] = field(default_factory=list)
    text: str = ""                  # all trusted text
    duplicate_of: str | None = None
    prior: dict[str, float] = field(default_factory=dict)
    data: bytes | None = None       # the bytes later stages read (the attachment, for emails)
    seconds: float = 0.0            # CPU seconds spent here


@lru_cache(maxsize=None)
def prior_for(fmt: str) -> dict[str, float]:
    """P(class | format) from the assumed class mix, floored so nothing is impossible."""
    mix = load("class_mix")["classes"]
    raw = {c: spec["share"] * spec["formats"].get(fmt, 0) / 100 for c, spec in mix.items()}
    floor = FLOOR * (sum(raw.values()) or 1)
    raw = {c: max(v, floor) for c, v in raw.items()}
    total = sum(raw.values())
    return {c: v / total for c, v in raw.items()}


def model_prior_for(fmt: str) -> dict[str, float]:
    """The same prior over the model's classes, with PoI and PoA merged into kyc_id (D24)."""
    return to_model_dist(prior_for(fmt))


def poa_share(fmt: str) -> float:
    """Prior share of Proof of Address among KYC documents of this format: the
    starting point for the address question (D24)."""
    p = prior_for(fmt)
    return p["proof_of_address"] / (p["proof_of_address"] + p["proof_of_identity"])


def _pdf_pages(data: bytes) -> list[PageInfo]:
    out = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            kind = pdf_page_kind(page)
            info = PageInfo(i, kind, page.rect.width, page.rect.height)
            if kind == "digital":
                info.text = page.get_text()
            else:
                imgs = page.get_images(full=True)
                if imgs:
                    xref, _, w, h, bpc, cs, *_rest = imgs[0]
                    info.source = (w, h, cs, bpc, _rest[-1] if _rest else "")
            out.append(info)
    return out


def _image_pages(data: bytes) -> list[PageInfo]:
    im = Image.open(io.BytesIO(data))
    return [PageInfo(i, "image", f.size[0], f.size[1], source=(f.size[0], f.size[1], f.mode)) for i, f in enumerate(ImageSequence.Iterator(im))]


def _office_text(data: bytes, kind: str) -> tuple[str, int]:
    """Text of a DOCX, XLSX or PPTX, and how many pictures it embeds."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        media = sum(1 for n in z.namelist() if "/media/" in n)
    if kind == "DOCX":
        import docx
        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells]
    elif kind == "XLSX":
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        parts = [str(v) for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for v in row if v is not None]
    else:
        from pptx import Presentation
        parts = [sh.text_frame.text for s in Presentation(io.BytesIO(data)).slides for sh in s.shapes if sh.has_text_frame]
    return "\n".join(parts), media


def analyse(data: bytes) -> tuple[str, list[PageInfo], str, bytes]:
    """True type, pages, trusted text, and the bytes later stages should read."""
    t = sniff(data[:2048])
    if t == "ZIP":
        try:
            t = office_kind(io.BytesIO(data))
        except zipfile.BadZipFile:
            return "UNKNOWN", [], "", data
        if t == "ZIP":  # an archive: classify its first member
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                if names:
                    inner_type, pages, text, inner = analyse(z.read(names[0]))
                    return "ZIP", pages, text, inner
            return "ZIP", [], "", data
    if t == "PDF":
        pages = _pdf_pages(data)
        return t, pages, "\n".join(p.text for p in pages), data
    if t in ("JPG", "PNG", "TIFF"):
        return t, _image_pages(data), "", data
    if t in ("DOCX", "XLSX", "PPTX"):
        text, media = _office_text(data, t)
        if len(text.strip()) < MIN_VISIBLE_CHARS and media:  # a pasted picture with little text (D19)
            return t, [PageInfo(0, "image", 0, 0)], text, data
        return t, [PageInfo(0, "digital", 0, 0, text=text)], text, data
    if t == "EML":
        msg = email.message_from_bytes(data, policy=policy.default)
        body = msg.get_body(preferencelist=("plain",))
        text = f"{msg.get('subject', '')}\n{body.get_content() if body else ''}"
        for part in msg.iter_attachments():
            inner_type, pages, inner_text, inner = analyse(part.get_payload(decode=True))
            return "EML", pages, (inner_text or ""), inner
        return "EML", [PageInfo(0, "digital", 0, 0, text=text)], text, data
    if t == "TXT":
        text = data.decode("utf-8", "replace")
        return t, [PageInfo(0, "digital", 0, 0, text=text)], text, data
    return t, [], "", data


def open_file(key: str, data: bytes, checksum: str, seen: dict[str, str]) -> L0Result:
    t0 = time.process_time()
    if checksum in seen:
        return L0Result(key, "", "", "duplicate", duplicate_of=seen[checksum], seconds=time.process_time() - t0)
    seen[checksum] = key
    true_type, pages, text, inner = analyse(data)
    kinds = {p.kind for p in pages}
    has_text = len(text.strip()) >= MIN_VISIBLE_CHARS
    if "digital" in kinds and len(kinds) > 1:
        route = "mixed"
    elif has_text and kinds <= {"digital"}:
        route = "text"
    else:
        route = "image"
    fmt = TYPE_TO_FORMAT.get(true_type, "OTH")
    return L0Result(key, true_type, fmt, route, pages, text, None, prior_for(fmt), inner, time.process_time() - t0)
