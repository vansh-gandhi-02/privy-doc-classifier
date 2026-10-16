"""What a file really is, and whether its text can be trusted (walkthrough step 1).

- True type comes from the first bytes, not the extension.
- A PDF page is "digital" only if it has enough visible text drawn on top of
  everything else. Invisible text (scanner OCR layers) and text hidden under a
  full-page image are not trusted, so those pages count as scans (D19). Hidden
  text is also where someone would plant words to fool the classifier or the LLM.
"""
from __future__ import annotations

import zipfile

import pymupdf

MAGIC = [
    (b"%PDF", "PDF"),
    (b"\xff\xd8\xff", "JPG"),
    (b"\x89PNG", "PNG"),
    (b"II*\x00", "TIFF"),
    (b"MM\x00*", "TIFF"),
    (b"PK\x03\x04", "ZIP"),           # DOCX, XLSX, PPTX and plain ZIP, told apart by contents
    (b"\xd0\xcf\x11\xe0", "OLE"),     # Outlook .msg, old .doc and .xls
]
MIN_VISIBLE_CHARS = 50
FULL_PAGE = 0.8  # an image covering 80% of the page counts as a scan


def sniff(head: bytes) -> str:
    for sig, kind in MAGIC:
        if head.startswith(sig):
            return kind
    text = head[:1024].decode("latin-1", "ignore")
    if any(h in text for h in ("MIME-Version:", "Received:", "\nFrom:", "Subject:")):
        return "EML"
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
    return "TXT" if text and printable / len(text) > 0.95 else "UNKNOWN"


def office_kind(path) -> str:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    for prefix, kind in (("word/", "DOCX"), ("xl/", "XLSX"), ("ppt/", "PPTX")):
        if any(n.startswith(prefix) for n in names):
            return kind
    return "ZIP"


def visible_chars(page: pymupdf.Page) -> int:
    """Characters a reader can actually see: drawn visibly (not render mode 3)
    and after the last full-page image, so not covered by it."""
    area = page.rect.get_area()
    last_cover = -1
    for i, (kind, bbox) in enumerate(page.get_bboxlog()):
        if kind == "fill-image" and (pymupdf.Rect(bbox) & page.rect).get_area() >= FULL_PAGE * area:
            last_cover = i
    return sum(
        len(span["chars"])
        for span in page.get_texttrace()
        if span["type"] != 3 and span.get("opacity", 1) > 0 and span["seqno"] > last_cover
    )


def pdf_page_kind(page: pymupdf.Page) -> str:
    return "digital" if visible_chars(page) >= MIN_VISIBLE_CHARS else "scan"
