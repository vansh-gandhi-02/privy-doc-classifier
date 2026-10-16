"""Building blocks shared by the templates: issuer headers, centred text,
checkbox rows, and Flow, which lays out running prose across pages."""
from __future__ import annotations

import math
import random

import pymupdf

from docgen.layout import A4, BLACK, FONTS, GREY, WHITE, Page, P, R, Style, T

LIGHT = (0.93, 0.93, 0.93)


def text_width(s: str, size: float, font: str = "helv", bold: bool = False) -> float:
    return pymupdf.get_text_length(s, fontname=FONTS[font][1 if bold else 0], fontsize=size)


def centered(s: str, y: float, size: float, st: Style | None = None, bold: bool = False, width: float = A4[0],
             color=BLACK, x0: float = 0) -> dict:
    font = st.font if st else "helv"
    return T(x0 + (width - text_width(s, size, font, bold)) / 2, y, s, size=size, bold=bold, color=color)


def initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:3] if w[0].isalpha()).upper()


def header(pg: Page, st: Style, name: str, lines: list[str] = (), y: float = 40, width: float = A4[0]) -> float:
    """Issuer header: optional colour band, logo box left or right, name and
    address lines. Returns the y below it."""
    h = 34 + 9 * len(lines)
    on_band = st.band
    if on_band:
        pg.add(R(0, 0, width, y + h - 14, fill=st.accent, stroke=None))
    ink = WHITE if on_band else st.accent
    lx = width - 84 if st.logo_right else 36
    pg.add(R(lx, y - 16, 46, 32, fill=None if on_band else st.accent, stroke=WHITE if on_band else None, lw=1.2))
    pg.add(T(lx + 7, y + 4, initials(name)[:3], size=11, bold=True, color=WHITE))
    nx = 36 if st.logo_right else 94
    pg.add(T(nx, y, name, size=15, bold=True, color=ink))
    for i, line in enumerate(lines):
        pg.add(T(nx, y + 13 + 9 * i, line, size=7, color=WHITE if on_band else GREY))
    return y + h


def section(pg: Page, st: Style, y: float, title: str, x: float = 36, w: float = 523) -> float:
    pg.add(R(x, y, w, 13, fill=st.accent, stroke=None), T(x + 5, y + 9.5, title, size=8, bold=True, color=WHITE))
    return y + 22


def checks(x: float, y: float, options: list[str], chosen: str | None, size: float = 7.5) -> list[dict]:
    from docgen.layout import CHECK
    out, cx = [], x
    for o in options:
        out.append(CHECK(cx, y - size + 1, size, o == chosen))
        out.append(T(cx + size + 3, y, o, size=size))
        cx += size + 8 + text_width(o, size)
    return out


def maybe(rng: random.Random, p: float, value, default=None):
    return value if rng.random() < p else default


class Flow:
    """Lays out headings and paragraphs top to bottom, starting new pages as
    needed. Templates with running prose (contracts, deeds, reports) use it."""

    def __init__(self, st: Style, first: Page | None = None, y: float = 60, x: float = 54, w: float = 487,
                 bottom: float = 800, size=A4):
        self.st, self.x, self.w, self.bottom, self.size = st, x, w, bottom, size
        self.pages = [first or Page(size)]
        self.y = y

    @property
    def page(self) -> Page:
        return self.pages[-1]

    def new_page(self) -> None:
        self.pages.append(Page(self.size))
        self.y = 60

    def need(self, h: float) -> float:
        if self.y + h > self.bottom:
            self.new_page()
        y = self.y
        self.y += h
        return y

    def _height(self, text: str, size: float) -> float:
        per_line = self.w / (size * (0.47 if self.st.font == "tiro" else 0.52))
        lines = sum(max(1, math.ceil(len(part) / per_line)) for part in text.split("\n"))
        return (lines + 1) * size * 1.25

    def para(self, text: str, size: float = 9, bold: bool = False, align: int = 3, gap: float = 4) -> None:
        h = self._height(text, size)
        y = self.need(h + gap)
        self.page.add(P(self.x, y, self.w, h, text, size=size, bold=bold, align=align))

    def heading(self, text: str, size: float = 10.5, center: bool = True, gap: float = 8) -> None:
        y = self.need(size * 1.6 + gap)
        x = self.x + (self.w - text_width(text, size, self.st.font, True)) / 2 if center else self.x
        self.page.add(T(x, y + size, text, size=size, bold=True))

    def gap(self, h: float) -> None:
        self.y += h
