"""Split a multi-page file into the documents it contains (DECISIONS D21).

Every page already has its L1 description. Between each pair of neighbouring
pages we measure how much changes:
- layout similarity (DiT summaries) and how far apart their L1 class guesses are
- whether the new page looks like a first page (a small model trained on
  first pages vs continuation pages)
- free physical cues from L0: page size or shape changes, digital <-> scan,
  a different scanner fingerprint
A small logistic regression turns these into P(a new document starts here).
A boundary needs that probability above a threshold tuned on the calibration
split; unsure pages stay with the current document (continuation pages carry
no title). Printed page numbers ("Page 2 of 6") overrule the layout model (D30).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

EMB = slice(0, 768)
# "Page 2", "Page 2 of 6", "PAGE NO. 2/6", "Page:2" (OCR often drops the spaces)
PAGE_NO = re.compile(r"\bpage\s*(?:no\.?)?\s*[:\-]?\s*(\d{1,3})(?:\s*(?:of|/)\s*\d{1,3})?\b", re.I)


def page_number(text: str | None) -> int | None:
    m = PAGE_NO.search(text or "")
    return int(m.group(1)) if m else None


def page_cue_texts(l0, max_pages: int = 12) -> tuple[list[str], float]:
    """The text the splitter checks for page numbers, page by page: trusted text on
    digital pages (free), the top and bottom lines of scanned pages (pipeline/l2_text/ocr.py).
    Returns the texts and the CPU seconds spent reading."""
    from pipeline.l2_text.ocr import page_cue_read, page_image
    texts, secs = [], 0.0
    for i, p in enumerate(l0.pages[:max_pages]):
        if p.kind == "digital":
            texts.append(p.text)
        else:
            r = page_cue_read(page_image(l0.data, i))
            texts.append(r.text)
            secs += r.seconds
    return texts, secs


def file_cue_texts(path: str) -> tuple[str, list[str], float]:
    """page_cue_texts for a file on disk (top-level, so a process pool can run it)."""
    from pipeline.l0_open.metadata import open_file
    data = open(path, "rb").read()
    texts, secs = page_cue_texts(open_file(path, data, "", {}))
    return path, texts, secs


def _unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def pair_features(prev_f, cur_f, prev_p, cur_p, prev_meta, cur_meta, first_score: float) -> np.ndarray:
    """prev/cur: page features, L1 class probabilities, and (kind, w, h, source)."""
    cos = float(_unit(prev_f[EMB]) @ _unit(cur_f[EMB]))
    m = 0.5 * (prev_p + cur_p)
    js = float(0.5 * np.sum(prev_p * np.log((prev_p + 1e-12) / (m + 1e-12))) + 0.5 * np.sum(cur_p * np.log((cur_p + 1e-12) / (m + 1e-12))))
    (pk, pw, ph, ps), (ck, cw, chh, cs) = prev_meta, cur_meta
    shape = abs(np.log((pw + 1e-6) / (ph + 1e-6)) - np.log((cw + 1e-6) / (chh + 1e-6)))
    area = abs(np.log((pw * ph + 1e-6) / (cw * chh + 1e-6)))
    return np.array([cos, js, float(prev_p.argmax() != cur_p.argmax()), first_score, shape, area,
                     float(pk != ck), float(ps != cs and pk == ck == "scan")], dtype=np.float32)


@dataclass
class BoundaryModel:
    first_scaler: object
    first_clf: object        # P(page is a document's first page), from the page description
    pair_clf: object         # P(new document starts here), from pair_features
    threshold: float

    def first_scores(self, feats: np.ndarray) -> np.ndarray:
        return self.first_clf.predict_proba(self.first_scaler.transform(feats))[:, 1]

    def boundaries(self, feats: np.ndarray, probs: np.ndarray, meta: list[tuple]) -> list[float]:
        """P(new document starts) for pages 2..n of one file."""
        if len(feats) < 2:
            return []
        fs = self.first_scores(feats)
        X = np.stack([pair_features(feats[i - 1], feats[i], probs[i - 1], probs[i], meta[i - 1], meta[i], fs[i]) for i in range(1, len(feats))])
        return list(self.pair_clf.predict_proba(X)[:, 1])

    def segments(self, feats: np.ndarray, probs: np.ndarray, meta: list[tuple], page_texts: list[str] | None = None) -> list[tuple[int, int]]:
        """(start, end) page ranges, 0-based and inclusive. With page texts, printed
        page numbers overrule the layout model (D30): "Page 3" cannot start a document,
        "Page 1" always does."""
        cuts = {i + 1 for i, p in enumerate(self.boundaries(feats, probs, meta)) if p >= self.threshold}
        if page_texts:
            for i in range(1, min(len(feats), len(page_texts))):
                k = page_number(page_texts[i])
                if k is not None and k > 1:
                    cuts.discard(i)
                elif k == 1:
                    cuts.add(i)
        cuts = sorted(cuts)
        starts = [0] + cuts
        ends = [s - 1 for s in cuts] + [len(feats) - 1]
        return list(zip(starts, ends))
