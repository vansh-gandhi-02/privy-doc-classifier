"""Train, calibrate and check L1 (layout) on the dev sample.

- trains logistic regression on every train-split page (label = the page's model
  class: PoI and PoA are one class, kyc_id, split later by the address question, D24)
- picks the regularisation strength and the temperature on the calibration split
- reports on dev-test first pages: layout alone, then combined with the format prior
  the way the pipeline will use it: how many documents L1 settles at 95%, how
  accurate those are, how many it can only narrow to a bucket, and which pairs
  it confuses, including the cross-bucket rate that tests DECISIONS D4

Run: python -m scripts.train_l1
"""
from __future__ import annotations

import csv
import json
from collections import Counter

import joblib
import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler

from common.config import DATA_DIR, bucket_of, model_class_ids, model_merge, to_model_class
from pipeline.posterior import Posterior
from pipeline.l0_open.metadata import model_prior_for
from pipeline.l1_layout.layout import LayoutModel

THRESHOLD = 0.95


def _nll(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1))))


def _ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(total)


def main() -> None:
    root = DATA_DIR / "sample"
    d = np.load(root / "pages.npz")
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    classes = model_class_ids()
    idx = {c: i for i, c in enumerate(classes)}
    y = np.array([idx[to_model_class(c)] for c in d["cls"]])
    X, split, first = d["feats"], d["split"], d["first"]
    tr, ca, te = split == "train", (split == "calib") & first, (split == "dev_test") & first
    scaler = StandardScaler().fit(X[tr])
    best = None
    for C in (0.003, 0.01, 0.03, 0.1, 0.3):
        clf = LogisticRegression(C=C, max_iter=4000).fit(scaler.transform(X[tr]), y[tr])
        nll = _nll(clf.predict_proba(scaler.transform(X[ca])), y[ca])
        print(f"  C={C:<6} calib NLL {nll:.3f}")
        if best is None or nll < best[0]:
            best = (nll, C, clf)
    _, C, clf = best
    logits = clf.decision_function(scaler.transform(X[ca]))

    def nll_t(t):
        z = logits / t
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        return _nll(p / p.sum(axis=1, keepdims=True), y[ca])

    temp = float(minimize_scalar(nll_t, bounds=(0.05, 10), method="bounded").x)
    train_prior = np.bincount(y[tr], minlength=len(classes)) / tr.sum()
    model = LayoutModel(classes, scaler, clf, temp, train_prior)
    (DATA_DIR / "models").mkdir(exist_ok=True)
    joblib.dump(model, DATA_DIR / "models" / "l1.joblib")

    p = model.proba(X[te])
    pred, conf = p.argmax(1), p.max(1)
    buckets = bucket_of()
    top2 = (np.argsort(-p, axis=1)[:, :2] == y[te][:, None]).any(1).mean()
    print(f"\nchosen C={C}, temperature {temp:.2f}")
    print(f"layout alone, dev-test first pages (n={te.sum()}): accuracy {np.mean(pred == y[te]):.3f}, top-2 {top2:.3f}, "
          f"bucket accuracy {np.mean([buckets[classes[a]] == buckets[classes[b]] for a, b in zip(pred, y[te])]):.3f}, "
          f"macro-F1 {f1_score(y[te], pred, average='macro'):.3f}, calibration error {_ece(conf, pred == y[te]):.3f}")

    # Combined with the format prior, as the pipeline does: accept, lock bucket, or escalate.
    keys = d["key"][te]
    outcomes, accepted_ok, locked_ok, cross = Counter(), [], [], 0
    per_class = {c: Counter() for c in classes}
    for k, lik, true in zip(keys, model.likelihood(X[te]), y[te]):
        lab = labels[k]
        fmt = "PDF" if lab["subtype"] == "bundle" else lab["fmt"]
        post = Posterior.from_prior(model_prior_for(fmt), needs_split=tuple(model_merge()))
        post.update("L1", lik)
        dec = post.decide(THRESHOLD, buckets)
        if dec.action == "lock_bucket" and post.top()[0] in model_merge():
            # the type is settled (a KYC ID document); only the address question is left (D24)
            dec = type(dec)("accept", label=post.top()[0], bucket=dec.bucket, confidence=dec.confidence)
        outcomes[dec.action] += 1
        per_class[classes[true]][dec.action] += 1
        if dec.action == "accept":
            accepted_ok.append(dec.label == classes[true])
        elif dec.action == "lock_bucket":
            locked_ok.append(dec.bucket == buckets[classes[true]])
        top = post.top()[0]
        cross += buckets[top] != buckets[classes[true]]
    n = te.sum()
    print(f"\nwith the format prior, threshold {THRESHOLD}:")
    print(f"  type settled by L1: {outcomes['accept'] / n:.1%} (accuracy {np.mean(accepted_ok):.3f}; KYC ones go to the address question)")
    print(f"  bucket locked:  {outcomes['lock_bucket'] / n:.1%} (bucket right {np.mean(locked_ok) if locked_ok else float('nan'):.3f})")
    print(f"  escalated:      {outcomes['escalate'] / n:.1%}")
    print(f"  cross-bucket confusion of the top class (D4 test, regroup if > 1-2%): {cross / n:.1%}")
    print("\nper class (accept / lock / escalate):")
    for c in classes:
        o = per_class[c]
        t = sum(o.values()) or 1
        print(f"  {c:22} {o['accept'] / t:5.0%} {o['lock_bucket'] / t:5.0%} {o['escalate'] / t:5.0%}   n={sum(o.values())}")
    pairs = Counter((classes[a], classes[b]) for a, b in zip(y[te], pred) if a != b)
    print("\nmost confused (true -> predicted, layout alone):", pairs.most_common(8))
    json.dump({"C": C, "temperature": temp, "accuracy": float(np.mean(pred == y[te])), "accept_rate": outcomes["accept"] / n,
               "accepted_accuracy": float(np.mean(accepted_ok)), "lock_rate": outcomes["lock_bucket"] / n, "escalate_rate": outcomes["escalate"] / n,
               "cross_bucket": cross / n}, open(root / "l1_metrics.json", "w"), indent=1)


if __name__ == "__main__":
    main()
