"""L2: text (walkthrough step 3, DECISIONS D23 and D24).

One model over the 15 model classes (PoI and PoA merged into kyc_id) answers
"which class is this text?". Inputs:
- 3-5 letter pieces of the normalised text (pipeline/l2_text/features.py), which survive
  OCR typos and OCR running words together
- ID evidence (checksum-valid / pattern-only counts, IDs per line), learned like
  words, never used as a verdict

Calibration: one temperature per reading depth ("view"), fitted on the
calibration split, because a selective read (a few top lines) and a whole
digital document are different amounts of evidence.

Evidence, not a second prior: the model's output is divided by its training
class mix before it is multiplied into the posterior (D23, 3c).

Each rung replaces the text evidence instead of adding to it: a full read
contains the selective read's lines, so multiplying both would count them twice.

The discriminator table for any pair A, B is the gap between their weight rows,
w_A - w_B: shared words weigh the same in both rows and cancel (the passbook point).

Reading order (D20, D22): text files use their free text first. Scans go
selective read -> full page -> next informative page and last page -> L3. KYC
documents always get a full read for the address question (D24, option A).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse

from pipeline.l2_text.features import ID_NAMES, id_features, normalise

VIEWS = ("native", "sel", "full1", "more")


@dataclass
class TextModel:
    classes: list[str]
    vec: object          # TfidfVectorizer over letter pieces
    id_scaler: object    # StandardScaler over ID features
    clf: object          # multinomial LogisticRegression
    temps: dict[str, float]
    train_prior: np.ndarray

    def features(self, texts: list[str]):
        words = self.vec.transform([normalise(t) for t in texts])
        idf = self.id_scaler.transform(np.stack([id_features(t) for t in texts]))
        return sparse.hstack([words, sparse.csr_matrix(idf)]).tocsr()

    def logits(self, texts: list[str]) -> np.ndarray:
        return self.clf.decision_function(self.features(texts))

    def proba(self, texts: list[str], view: str) -> np.ndarray:
        z = self.logits(texts) / self.temps.get(view, 1.0)
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        return p / p.sum(axis=1, keepdims=True)

    def likelihood(self, texts: list[str], view: str) -> list[dict[str, float]]:
        """P(class | text) / P_train(class): evidence with the training mix removed."""
        ratio = self.proba(texts, view) / self.train_prior
        return [dict(zip(self.classes, r / r.max())) for r in ratio]

    def feature_names(self) -> list[str]:
        return list(self.vec.get_feature_names_out()) + [f"ID:{n}" for n in ID_NAMES]

    def discriminators(self, a: str, b: str, k: int = 12) -> dict[str, list[tuple[str, float]]]:
        """The features that most separate class a from class b, each way."""
        w = self.clf.coef_
        gap = w[self.classes.index(a)] - w[self.classes.index(b)]
        names = self.feature_names()
        order = np.argsort(gap)
        return {a: [(names[i], round(float(gap[i]), 2)) for i in order[::-1][:k]],
                b: [(names[i], round(float(-gap[i]), 2)) for i in order[:k]]}
