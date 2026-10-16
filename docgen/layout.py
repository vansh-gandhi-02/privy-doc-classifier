"""Page model shared by all templates: a document is pages of simple blocks.

Templates describe a document once, as blocks. render.py draws the blocks into
a PDF (and from there into scans and photos), and the DOCX, XLSX, TXT, PPTX and
EML writers walk the same blocks in reading order. One description, every format.

Sizes are in PDF points (1/72 inch).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

A4 = (595.0, 842.0)
ID1 = (242.6, 153.0)       # ID cards: 85.6 x 54 mm
ID3 = (354.3, 249.4)       # passport page: 125 x 88 mm
CHEQUE = (575.0, 261.0)    # 203 x 92 mm
PASSBOOK = (430.0, 270.0)  # a printed passbook page, landscape

BLACK = (0, 0, 0)
GREY = (0.45, 0.45, 0.45)
WHITE = (1, 1, 1)


@dataclass
class Page:
    size: tuple[float, float] = A4
    blocks: list[dict] = field(default_factory=list)
    bg: tuple | None = None  # background tint

    def add(self, *blocks: dict) -> Page:
        self.blocks.extend(b for b in blocks if b)
        return self


@dataclass
class Doc:
    title: str
    pages: list[Page]
    font: str = "helv"


# Base-14 font families: (regular, bold). Base-14 fonts cover Latin-1 only, so
# templates write "Rs." rather than the rupee sign.
FONTS = {"helv": ("helv", "hebo"), "tiro": ("tiro", "tibo"), "cour": ("cour", "cobo")}
ACCENTS = [(0.05, 0.2, 0.5), (0.6, 0.05, 0.1), (0.0, 0.4, 0.3), (0.35, 0.1, 0.45), (0.75, 0.35, 0.0)]


@dataclass
class Style:
    """Visual variant of a template. Variant 3 never appears in training (D15),
    so the test set always contains layouts the models have not seen."""
    variant: int
    font: str
    accent: tuple
    band: bool
    logo_right: bool


def style_for(rng: random.Random, variant: int) -> Style:
    font = ["helv", "tiro", "helv", "tiro"][variant]
    band = variant in (1, 3)
    logo_right = variant in (2, 3)
    accent = ACCENTS[(variant + rng.randint(0, 1)) % len(ACCENTS)]
    return Style(variant, font, accent, band, logo_right)


# Block constructors. Templates only ever build pages out of these.
def T(x, y, s, size=9, bold=False, color=BLACK, font=None, rot=0):
    """One line of text; y is the baseline."""
    return dict(k="text", x=x, y=y, s=str(s), size=size, bold=bold, color=color, font=font, rot=rot)


def P(x, y, w, h, s, size=8.5, bold=False, align=0, font=None, color=BLACK):
    """A wrapped paragraph inside a box. Shrinks the font until it fits."""
    return dict(k="para", x=x, y=y, w=w, h=h, s=str(s), size=size, bold=bold, align=align, font=font, color=color)


def KV(x, y, pairs, size=8.5, lw=110, lh=None, font=None, vfont=None, color=BLACK):
    """Label: value rows. vfont lets filled-in values use a different font (forms)."""
    return dict(k="kv", x=x, y=y, pairs=[(str(a), str(b)) for a, b in pairs], size=size, lw=lw,
                lh=lh or size * 1.55, font=font, vfont=vfont, color=color)


def TB(x, y, widths, rows, size=7.5, header=True, ruled=True, rh=None, font=None, align=None):
    """A table. rows[0] is the header when header=True. align: per column, 0 left, 2 right."""
    return dict(k="table", x=x, y=y, widths=list(widths), rows=[[str(c) for c in r] for r in rows],
                size=size, header=header, ruled=ruled, rh=rh or size * 1.75, font=font, align=align)


def R(x, y, w, h, fill=None, stroke=BLACK, lw=0.8):
    return dict(k="rect", x=x, y=y, w=w, h=h, fill=fill, stroke=stroke, lw=lw)


def L(x1, y1, x2, y2, color=BLACK, lw=0.6):
    return dict(k="line", x1=x1, y1=y1, x2=x2, y2=y2, color=color, lw=lw)


def PHOTO(x, y, w, h):
    """A passport-style photo: grey box with a head-and-shoulders silhouette."""
    return dict(k="photo", x=x, y=y, w=w, h=h)


def QR(x, y, s, seed):
    """A QR-like square of random modules with the three finder squares."""
    return dict(k="qr", x=x, y=y, s=s, seed=seed)


def SEAL(x, y, r, text, color=(0.2, 0.2, 0.6)):
    """A round rubber stamp centred on (x, y)."""
    return dict(k="seal", x=x, y=y, r=r, s=str(text), color=color)


def SIGN(x, y, w, seed, color=(0.1, 0.1, 0.45)):
    """A scribbled signature starting at (x, y)."""
    return dict(k="sign", x=x, y=y, w=w, seed=seed, color=color)


def THUMB(x, y, w, h):
    """A thumb impression (registration pages)."""
    return dict(k="thumb", x=x, y=y, w=w, h=h)


def EMBLEM(x, y, s, color=(0.3, 0.3, 0.3)):
    """A stand-in for a state emblem or board logo, centred on (x, y)."""
    return dict(k="emblem", x=x, y=y, s=s, color=color)


def CHECK(x, y, s, checked):
    return dict(k="check", x=x, y=y, s=s, checked=checked)


def BARS(x, y, w, h, seed):
    """Barcode-like vertical bars."""
    return dict(k="bars", x=x, y=y, w=w, h=h, seed=seed)
