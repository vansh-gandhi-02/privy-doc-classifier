"""L1: the page's layout, without OCR (walkthrough step 2, DECISIONS D20).

Each page is rendered small and described by:
- DiT (microsoft/dit-base-finetuned-rvlcdip, MIT licence), used frozen: its
  768-number summary of the page plus its 16 RVL-CDIP scores (letter, form,
  invoice, budget...). Pretrained on 42M real document images, so it is not
  tied to our generator's quirks.
- six readable signals, so a decision can be explained: page shape, how
  card-like the shape is (ID-1 ratio 1.586), QR code found, face found, ink
  density, colourfulness. The face detector will not fire on our synthetic
  silhouettes; it is there for real documents (stated limitation).

A small logistic regression on top gives P(class | page). It is calibrated by
temperature scaling on the calibration split, and handed to the posterior as a
likelihood ratio, P(class | page) / P_train(class), so the training mix does
not leak in as a hidden prior.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageSequence


MODEL_ID = "microsoft/dit-base-finetuned-rvlcdip"
LONG_SIDE = 448
_faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_qr = cv2.QRCodeDetector()


def render_pages(data: bytes, true_type: str, max_pages: int | None = None) -> list[Image.Image]:
    """Small RGB images of each page (PDF) or frame (image file)."""
    out = []
    if true_type in ("PDF", "ZIP", "EML") and data[:4] == b"%PDF":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                if max_pages and i >= max_pages:
                    break
                dpi = int(max(20, LONG_SIDE / (max(page.rect.width, page.rect.height) / 72)))
                pix = page.get_pixmap(dpi=dpi)
                out.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    else:
        im = Image.open(io.BytesIO(data))
        for i, frame in enumerate(ImageSequence.Iterator(im)):
            if max_pages and i >= max_pages:
                break
            f = frame.convert("RGB")
            f.thumbnail((LONG_SIDE, LONG_SIDE))
            out.append(f)
    return out


def signals(img: Image.Image, page_w: float, page_h: float) -> np.ndarray:
    w, h = (page_w, page_h) if page_w and page_h else img.size
    ratio = max(w, h) / max(min(w, h), 1)
    arr = np.asarray(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    try:
        qr = float(_qr.detect(gray)[0])
    except cv2.error:
        qr = 0.0
    faces = _faces.detectMultiScale(gray, 1.1, 5, minSize=(24, 24))
    return np.array([math.log(w / h), math.exp(-((ratio - 1.586) / 0.12) ** 2), qr, float(len(faces) > 0),
                     float((gray < 128).mean()), float(hsv[:, :, 1].mean() / 255)], dtype=np.float32)


class Embedder:
    """DiT, frozen. Returns [768 pooled summary | 16 RVL-CDIP logits] per image."""

    def __init__(self, device: str | None = None):
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        self.torch = torch
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.proc = AutoImageProcessor.from_pretrained(MODEL_ID)
        self.model = AutoModelForImageClassification.from_pretrained(MODEL_ID).eval().to(self.device)

    def __call__(self, images: list[Image.Image], batch: int = 32) -> np.ndarray:
        outs = []
        with self.torch.no_grad():
            for i in range(0, len(images), batch):
                x = self.proc(images=images[i:i + batch], return_tensors="pt")["pixel_values"].to(self.device)
                base = self.model.beit(pixel_values=x)
                logits = self.model.classifier(base.pooler_output)
                outs.append(self.torch.cat([base.pooler_output, logits], dim=1).float().cpu().numpy())
        return np.concatenate(outs) if outs else np.zeros((0, 784), np.float32)


@dataclass
class LayoutModel:
    """Scaler + logistic regression + temperature, trained by scripts/train_l1.py."""
    classes: list[str]
    scaler: object
    clf: object
    temperature: float
    train_prior: np.ndarray

    def proba(self, features: np.ndarray) -> np.ndarray:
        logits = self.clf.decision_function(self.scaler.transform(features)) / self.temperature
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def likelihood(self, features: np.ndarray) -> list[dict[str, float]]:
        """P(class | page) / P_train(class): evidence with the training mix removed."""
        ratio = self.proba(features) / self.train_prior
        return [dict(zip(self.classes, r / r.max())) for r in ratio]
