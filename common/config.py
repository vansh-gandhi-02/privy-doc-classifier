"""Load the YAML files in config/ by name, plus a few lookups used everywhere."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def class_ids(scored_only: bool = False) -> list[str]:
    classes = load("classes")["classes"]
    return [c for c, spec in classes.items() if spec["scored"] or not scored_only]


def bucket_of() -> dict[str, str]:
    """Bucket of every brief class and every merged model class (D24)."""
    out = {c: spec["bucket"] for c, spec in load("classes")["classes"].items()}
    out.update({m: spec["bucket"] for m, spec in load("classes").get("model_merge", {}).items()})
    return out


def model_merge() -> dict[str, list[str]]:
    """Merged model class -> the brief classes it stands for (D24: kyc_id -> PoI, PoA)."""
    return {m: spec["members"] for m, spec in load("classes").get("model_merge", {}).items()}


def to_model_class(label: str) -> str:
    for m, members in model_merge().items():
        if label in members:
            return m
    return label


def model_class_ids() -> list[str]:
    """The 15 classes L1 and L2 choose from: the brief's classes with merges applied."""
    out: list[str] = []
    for c in class_ids():
        m = to_model_class(c)
        if m not in out:
            out.append(m)
    return out


def to_model_dist(dist: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for c, p in dist.items():
        m = to_model_class(c)
        out[m] = out.get(m, 0.0) + p
    return out


def critical_classes() -> list[str]:
    return [c for c, spec in load("classes")["classes"].items() if spec["critical"]]


def class_of_subtype() -> dict[str, str]:
    return {s: spec["class"] for s, spec in load("subtypes")["subtypes"].items()}
