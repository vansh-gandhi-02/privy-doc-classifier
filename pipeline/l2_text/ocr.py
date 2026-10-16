"""The reading ladder (DECISIONS D20): read as little as possible, more only while unsure.

Measured on one core of the Mac (D20): reading every line of a dense page costs
~12.7 s, finding all text boxes costs under 1 s, and reading one line ~0.2 s.
So each rung finds boxes cheaply and reads only what it needs:

  rung 1  first informative page: skip near-blank pages (ink density, free)
  rung 2  selective read: every box found, read the top lines plus the largest
          lines in the top 40% of the page (titles are big and near the top)
  rung 3  read the whole page
  rung 4  read the next informative page and the last page
  rung 5  hand over to the LLM (not here)

Which rung a document stops at is decided by the posterior, not here: this
module only reads. Every read reports the CPU seconds it used, for the bench.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass

import numpy as np
import pymupdf
from PIL import Image, ImageSequence

OCR_LONG_SIDE = 1600
BLANK_INK = 0.004   # fraction of dark pixels below which a page counts as blank
TOP_LINES, BIG_LINES = 4, 3

_engine = None


def _ocr():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)  # one core, so CPU time is honest
    return _engine


@dataclass
class Read:
    text: str
    lines_found: int
    lines_read: int
    seconds: float


def page_image(data: bytes, index: int) -> Image.Image:
    """One page at OCR resolution."""
    if data[:4] == b"%PDF":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            page = doc[index]
            pix = page.get_pixmap(dpi=int(OCR_LONG_SIDE / (max(page.rect.width, page.rect.height) / 72)))
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    frame = next(f for i, f in enumerate(ImageSequence.Iterator(Image.open(io.BytesIO(data)))) if i == index).convert("RGB")
    frame.thumbnail((OCR_LONG_SIDE, OCR_LONG_SIDE))
    return frame


def is_blank(thumb: Image.Image) -> bool:
    return float((np.asarray(thumb.convert("L")) < 128).mean()) < BLANK_INK


def informative_pages(thumbs: list[Image.Image]) -> list[int]:
    return [i for i, t in enumerate(thumbs) if not is_blank(t)]


def _crop(arr: np.ndarray, box) -> np.ndarray:
    xs, ys = [int(p[0]) for p in box], [int(p[1]) for p in box]
    return arr[max(min(ys) - 2, 0): max(ys) + 2, max(min(xs) - 2, 0): max(xs) + 2]


def selective_read(img: Image.Image) -> Read:
    t0 = time.process_time()
    arr = np.asarray(img.convert("RGB"))
    boxes, _ = _ocr()(arr, use_rec=False, use_cls=False)
    boxes = list(boxes) if boxes is not None else []
    h = arr.shape[0]
    top = sorted(boxes, key=lambda b: min(p[1] for p in b))[:TOP_LINES]
    upper = [b for b in boxes if min(p[1] for p in b) < 0.4 * h]
    big = sorted(upper, key=lambda b: -(max(p[1] for p in b) - min(p[1] for p in b)))[:BIG_LINES]
    chosen = []
    for b in top + big:
        if not any(b is c for c in chosen):
            chosen.append(b)
    texts = []
    for b in sorted(chosen, key=lambda b: min(p[1] for p in b)):
        res, _ = _ocr()(_crop(arr, b), use_det=False, use_cls=False)
        if res:
            texts.append(res[0][0])
    return Read("\n".join(texts), len(boxes), len(chosen), time.process_time() - t0)


def page_cue_read(img: Image.Image, lines: int = 2) -> Read:
    """Read only the top and bottom lines of a page, where page numbers sit
    ("Page 2 of 6"). Used by the bundle splitter on every scanned page of a
    multi-page file; costs about the same as the selective read."""
    t0 = time.process_time()
    arr = np.asarray(img.convert("RGB"))
    boxes, _ = _ocr()(arr, use_rec=False, use_cls=False)
    boxes = sorted(list(boxes) if boxes is not None else [], key=lambda b: min(p[1] for p in b))
    chosen = boxes[:lines] + [b for b in boxes[-lines:] if not any(b is c for c in boxes[:lines])]
    texts = []
    for b in chosen:
        res, _ = _ocr()(_crop(arr, b), use_det=False, use_cls=False)
        if res:
            texts.append(res[0][0])
    return Read("\n".join(texts), len(boxes), len(chosen), time.process_time() - t0)


def full_read(img: Image.Image) -> Read:
    t0 = time.process_time()
    res, _ = _ocr()(np.asarray(img.convert("RGB")), use_cls=False)
    res = res or []
    return Read("\n".join(r[1] for r in res), len(res), len(res), time.process_time() - t0)
