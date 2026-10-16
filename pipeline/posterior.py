"""Per-document class probabilities, updated step by step (DECISIONS D9).

Each document starts at a prior (the assumed class mix, adjusted for its file
format), never at zero. Every pipeline step multiplies in how likely its
evidence is under each class, then rescales so the probabilities sum to 1, so
probabilities can move down as well as up. This is Wald's sequential probability
ratio test in multi-class form: keep buying evidence until one answer is likely
enough to stop.

The document leaves the pipeline when its top class crosses the threshold. A
bucket can be locked earlier, when the summed probability of its classes
crosses the threshold, so later steps only choose within that bucket.

Cycle 1 multiplies likelihoods directly, which assumes each step's evidence is
independent of the last. If two steps read the same thing, this double counts
and documents cross the threshold too early. D10 replaces it with a calibrated
update once we have labelled data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# No class is ever exactly 0: Bayes multiplies, so a zero could never recover.
FLOOR = 1e-4


@dataclass
class Decision:
    action: str                    # "accept", "lock_bucket" or "escalate"
    label: str | None = None       # the accepted class
    bucket: str | None = None      # the locked bucket
    confidence: float = 0.0


@dataclass
class Posterior:
    """`classes` are the model's classes. A merged class (D24: kyc_id) stands for
    several labels and cannot be accepted until `split` says how its probability
    divides among them; until then it can only lock its bucket."""
    classes: list[str]
    probs: np.ndarray
    history: list[tuple[str, np.ndarray]] = field(default_factory=list)
    needs_split: tuple[str, ...] = ()
    sub: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_prior(cls, prior: dict[str, float], needs_split: tuple[str, ...] = ()) -> Posterior:
        classes = list(prior)
        probs = np.maximum(np.array([prior[c] for c in classes], dtype=float), FLOOR)
        probs /= probs.sum()
        return cls(classes, probs, [("prior", probs.copy())], tuple(needs_split))

    def copy(self) -> Posterior:
        return Posterior(list(self.classes), self.probs.copy(), list(self.history), self.needs_split, dict(self.sub))

    def update(self, step: str, likelihood: dict[str, float]) -> None:
        """Multiply in P(evidence | class). A class missing from `likelihood` gets
        1.0, meaning the evidence says nothing about it."""
        lik = np.array([max(likelihood.get(c, 1.0), FLOOR) for c in self.classes])
        self.probs = self.probs * lik
        self.probs /= self.probs.sum()
        self.history.append((step, self.probs.copy()))

    def split(self, merged: str, shares: dict[str, float]) -> None:
        """How a merged class divides among its labels, e.g. kyc_id -> {PoA: P(address), PoI: 1 - P(address)}."""
        self.sub[merged] = shares
        self.history.append((f"split {merged}", self.probs.copy()))

    def label_probs(self) -> dict[str, float]:
        """Probabilities over output labels: split merged classes are divided, unsplit ones stay whole."""
        out: dict[str, float] = {}
        for c, p in zip(self.classes, self.probs):
            if c in self.sub:
                for label, share in self.sub[c].items():
                    out[label] = float(p) * share
            else:
                out[c] = float(p)
        return out

    def prob(self, cls: str) -> float:
        if cls in self.classes:
            return float(self.probs[self.classes.index(cls)])
        return self.label_probs()[cls]

    def top(self) -> tuple[str, float]:
        return max(self.label_probs().items(), key=lambda kv: kv[1])

    def bucket_probs(self, bucket_of: dict[str, str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for c, p in zip(self.classes, self.probs):
            out[bucket_of[c]] = out.get(bucket_of[c], 0.0) + float(p)
        return out

    def decide(self, threshold: float, bucket_of: dict[str, str] | None = None) -> Decision:
        label, p = self.top()
        if p >= threshold and label in self.needs_split and label not in self.sub:
            return Decision("lock_bucket", bucket=bucket_of[label] if bucket_of else label, confidence=p)
        if p >= threshold:
            return Decision("accept", label=label, bucket=bucket_of[label] if bucket_of else None, confidence=p)
        if bucket_of:
            bucket, bp = max(self.bucket_probs(bucket_of).items(), key=lambda kv: kv[1])
            if bp >= threshold:
                return Decision("lock_bucket", bucket=bucket, confidence=bp)
        return Decision("escalate", confidence=p)
