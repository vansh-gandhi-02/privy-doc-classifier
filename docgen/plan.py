"""How many documents of each class and format the sample needs (DECISIONS D14).

Two parts:
- a core drawn at the assumed class mix, so cost per document is measured on a
  realistic format split
- a top-up so every class has enough examples to train, calibrate and test on
  (at 1.5% a 3,000-document core holds only 45 marksheets of each kind)

Accuracy is then reported with each document reweighted back to the assumed
mix, so the top-up does not flatter the rare classes.

Run: python -m docgen.plan
"""
from __future__ import annotations

import math

from common.config import load


def _largest_remainder(weights: dict, total: int) -> dict:
    """Integer counts proportional to `weights` that sum exactly to `total`."""
    s = sum(weights.values())
    raw = {k: total * w / s for k, w in weights.items()}
    counts = {k: math.floor(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[: total - sum(counts.values())]:
        counts[k] += 1
    return counts


def plan(core_size: int | None = None, min_per_class: int | None = None) -> dict:
    cfg, mix = load("sample"), load("class_mix")["classes"]
    core_size = core_size or cfg["core_size"]
    min_per_class = min_per_class or cfg["min_per_class"]

    cells = {(c, f): spec["share"] * pct for c, spec in mix.items() for f, pct in spec["formats"].items()}
    core = _largest_remainder(cells, core_size)

    topup: dict = {}
    for c, spec in mix.items():
        have = sum(n for (cc, _), n in core.items() if cc == c)
        if have < min_per_class:
            for f, n in _largest_remainder(spec["formats"], min_per_class - have).items():
                topup[(c, f)] = n
    return {"core": core, "topup": topup}


def class_weights(p: dict) -> dict[str, float]:
    """Per-document weight that maps the sample back to the assumed class mix."""
    mix = load("class_mix")["classes"]
    totals: dict[str, int] = {}
    for part in ("core", "topup"):
        for (c, _), n in p[part].items():
            totals[c] = totals.get(c, 0) + n
    n_sample = sum(totals.values())
    return {c: (mix[c]["share"] / 100) / (totals[c] / n_sample) for c in totals}


def main() -> None:
    p = plan()
    w = class_weights(p)
    print(f"{'class':22} {'core':>5} {'top-up':>7} {'total':>6} {'weight':>7}")
    grand = 0
    for c in load("class_mix")["classes"]:
        core = sum(n for (cc, _), n in p["core"].items() if cc == c)
        top = sum(n for (cc, _), n in p["topup"].items() if cc == c)
        grand += core + top
        print(f"{c:22} {core:>5} {top:>7} {core + top:>6} {w[c]:>7.2f}")
    print(f"{'total':22} {sum(p['core'].values()):>5} {sum(p['topup'].values()):>7} {grand:>6}")


if __name__ == "__main__":
    main()
