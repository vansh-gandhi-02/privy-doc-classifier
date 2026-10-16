"""Does the assumed class mix reproduce the brief's format split?

Run after any edit to config/class_mix.yaml: python -m scripts.check_mix
"""
from __future__ import annotations

import sys

from common.config import load

TOLERANCE = 0.3  # percentage points per format


def implied_format_split() -> dict[str, float]:
    implied: dict[str, float] = {}
    for spec in load("class_mix")["classes"].values():
        for fmt, pct in spec["formats"].items():
            implied[fmt] = implied.get(fmt, 0.0) + spec["share"] * pct / 100
    return implied


def problems() -> list[str]:
    mix, brief = load("class_mix")["classes"], load("brief")["format_split_pct"]
    out = []
    total = sum(spec["share"] for spec in mix.values())
    if abs(total - 100) > 1e-9:
        out.append(f"class shares sum to {total}, not 100")
    for c, spec in mix.items():
        s = sum(spec["formats"].values())
        if abs(s - 100) > 1e-9:
            out.append(f"{c}: format split sums to {s}, not 100")
    implied = implied_format_split()
    for fmt, want in brief.items():
        got = implied.get(fmt, 0.0)
        if abs(got - want) > TOLERANCE:
            out.append(f"{fmt}: implied {got:.2f}% vs brief {want}%")
    return out


def main() -> None:
    brief, implied = load("brief")["format_split_pct"], implied_format_split()
    print(f"{'format':7} {'brief':>6} {'implied':>8} {'diff':>6}")
    for fmt, want in brief.items():
        got = implied.get(fmt, 0.0)
        print(f"{fmt:7} {want:>6.1f} {got:>8.2f} {got - want:>+6.2f}")
    found = problems()
    print("\nOK" if not found else "\nPROBLEMS:\n  " + "\n  ".join(found))
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
