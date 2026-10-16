"""Make clean renders look like real scans, phone photos and screenshots.

scan:        grey or colour, slight skew, blur, speckle noise, contrast shift
phone_photo: document on a desk, perspective warp, uneven light, blur, colour cast
screenshot:  clean, with a phone status bar on top

Strength is drawn per document, so the sample runs from clean to barely
readable. Synthetic documents are still cleaner than real ones; the write-up
says so.
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

WHITE = (255, 255, 255)


def _noise(img: Image.Image, rng: random.Random, sigma: float) -> Image.Image:
    a = np.asarray(img).astype(np.float32)
    a += np.random.default_rng(rng.randint(0, 2**31)).normal(0, sigma, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def scan(img: Image.Image, rng: random.Random) -> Image.Image:
    out = img.convert("L").convert("RGB") if rng.random() < 0.65 else img.convert("RGB")
    out = out.rotate(rng.uniform(-2.5, 2.5), resample=Image.BICUBIC, fillcolor=WHITE)
    out = ImageEnhance.Contrast(out).enhance(rng.uniform(0.7, 1.15))
    out = ImageEnhance.Brightness(out).enhance(rng.uniform(0.92, 1.08))
    out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0, 1.1)))
    return _noise(out, rng, rng.uniform(0, 10))


def _perspective_coeffs(dst, src) -> list[float]:
    """Coefficients PIL needs to map each output pixel back to the source image."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs += [u, v]
    return np.linalg.solve(np.array(rows, float), np.array(rhs, float)).tolist()


def phone_photo(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    pad = int(0.09 * max(w, h))
    desk = tuple(int(c) for c in rng.choice([(120, 90, 60), (200, 195, 185), (60, 60, 65), (150, 120, 95), (225, 225, 220)]))
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), desk)
    canvas.paste(img.convert("RGB"), (pad, pad))
    cw, ch = canvas.size
    j = lambda s: rng.uniform(-0.06, 0.06) * s
    src = [(pad, pad), (pad + w, pad), (pad + w, pad + h), (pad, pad + h)]
    dst = [(pad + j(w), pad + j(h)), (pad + w + j(w), pad + j(h)), (pad + w + j(w), pad + h + j(h)), (pad + j(w), pad + h + j(h))]
    out = canvas.transform((cw, ch), Image.PERSPECTIVE, _perspective_coeffs(dst, src), Image.BICUBIC, fillcolor=desk)
    # Uneven light: a brightness ramp across the frame.
    ramp = np.linspace(rng.uniform(0.7, 0.95), rng.uniform(0.95, 1.1), cw if rng.random() < 0.5 else ch)
    a = np.asarray(out).astype(np.float32)
    a *= ramp[None, :, None] if len(ramp) == cw else ramp[:, None, None]
    a *= np.array([rng.uniform(0.95, 1.05), 1.0, rng.uniform(0.9, 1.02)])  # colour cast
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.4)))
    out = _noise(out, rng, rng.uniform(2, 9))
    scale = 1600 / max(out.size)
    return out.resize((int(out.size[0] * scale), int(out.size[1] * scale))) if scale < 1 else out


def screenshot(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    bar = int(h * 0.035)
    out = Image.new("RGB", (w, h + bar), (20, 20, 20))
    out.paste(img.convert("RGB"), (0, bar))
    ImageDraw.Draw(out).text((10, bar // 4), f"{rng.randint(9, 23)}:{rng.randint(10, 59)}", fill=WHITE)
    return out
