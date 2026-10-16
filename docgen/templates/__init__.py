"""Document templates: one function per sub-type (DECISIONS D18), varied by Style.

A template takes a random generator, a Style and the sub-type name, and
returns a Doc (pages of blocks). docgen/render.py turns that into a file.

Variety across issuers and layout variants matters more than polish. Layout
variant 3 never appears in training, only in Lockbox A, so the sealed test
always contains layouts the models have not seen.
"""
from __future__ import annotations

import random
from typing import Callable

from docgen.layout import Doc, Style

TEMPLATES: dict[str, Callable[[random.Random, Style, str], Doc]] = {}


def template(*subtypes: str):
    def register(fn):
        for s in subtypes:
            TEMPLATES[s] = fn
        return fn
    return register


def make(subtype: str, rng: random.Random, st: Style) -> Doc:
    return TEMPLATES[subtype](rng, st, subtype)


from docgen.templates import cards, education, finance, forms, legal, other  # noqa: E402,F401  (registers templates)
