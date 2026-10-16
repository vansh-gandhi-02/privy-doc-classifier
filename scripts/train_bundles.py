"""Train and check the bundle splitter (DECISIONS D21) on the dev sample.

Training pairs come from the train split: neighbouring pages inside single
documents (no boundary), neighbouring pages inside bundles (boundary at each
segment start), plus extra positives made by putting one document's last page
next to another document's first page, which is how merged files arise.
The threshold maximises boundary F1 on the calibration split.

Reports on dev-test: boundary precision and recall, how many bundles are split
exactly right, how often a single multi-page document is wrongly split, and how
often each correctly split segment then gets the right class from L1 + prior.

Run: python -m scripts.train_bundles
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from common.config import DATA_DIR, to_model_class
from pipeline.l1_layout.bundles import BoundaryModel, pair_features
from pipeline.posterior import Posterior
from pipeline.l0_open.metadata import model_prior_for

THRESHOLD_GRID = np.linspace(0.2, 0.9, 15)


def main() -> None:
    root = DATA_DIR / "sample"
    d = np.load(root / "pages.npz")
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    probs = l1.proba(d["feats"])
    meta = [(k, float(s[0]), float(s[1]), src) for k, s, src in zip(d["kind"], d["size"], d["source"])]
    files = defaultdict(list)
    for i, k in enumerate(d["key"]):
        files[k].append(i)
    for k in files:
        files[k].sort(key=lambda i: d["page"][i])

    tr = d["split"] == "train"
    first_scaler = StandardScaler().fit(d["feats"][tr])
    first_clf = LogisticRegression(C=0.05, max_iter=3000).fit(first_scaler.transform(d["feats"][tr]), d["first"][tr])
    fs = first_clf.predict_proba(first_scaler.transform(d["feats"]))[:, 1]

    def pairs_of(split):
        X, y = [], []
        for k, idx in files.items():
            if labels[k]["split"] != split:
                continue
            for a, b in zip(idx, idx[1:]):
                X.append(pair_features(d["feats"][a], d["feats"][b], probs[a], probs[b], meta[a], meta[b], fs[b]))
                y.append(bool(d["first"][b]))
        return X, y

    X, y = pairs_of("train")
    rng = random.Random(3)
    train_files = [idx for k, idx in files.items() if labels[k]["split"] == "train" and labels[k]["subtype"] != "bundle"]
    for _ in range(2000):  # synthetic merges: last page of one document, first page of another
        a, b = rng.sample(train_files, 2)
        X.append(pair_features(d["feats"][a[-1]], d["feats"][b[0]], probs[a[-1]], probs[b[0]], meta[a[-1]], meta[b[0]], fs[b[0]]))
        y.append(True)
    pair_clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(np.array(X), np.array(y))
    print(f"trained on {len(y)} page pairs ({sum(y)} boundaries)")

    Xc, yc = pairs_of("calib")
    pc = pair_clf.predict_proba(np.array(Xc))[:, 1]
    yc = np.array(yc)
    best = max(THRESHOLD_GRID, key=lambda t: _f1(pc >= t, yc))
    model = BoundaryModel(first_scaler, first_clf, pair_clf, float(best))
    joblib.dump(model, DATA_DIR / "models" / "bundles.joblib")
    print(f"threshold {best:.2f} (calibration boundary F1 {_f1(pc >= best, yc):.3f})")

    tp = fp = fn = 0
    exact = n_bundles = false_split = n_multi = seg_total = seg_right = 0
    for k, idx in files.items():
        lab = labels[k]
        if lab["split"] != "dev_test" or len(idx) < 2:
            continue
        segs = model.segments(d["feats"][idx], probs[idx], [meta[i] for i in idx])
        pred_starts = {s for s, _ in segs}
        true_starts = {j for j, i in enumerate(idx) if d["first"][i]}
        tp += len((pred_starts & true_starts) - {0})
        fp += len(pred_starts - true_starts)
        fn += len(true_starts - pred_starts)
        if lab["subtype"] == "bundle":
            n_bundles += 1
            exact += pred_starts == true_starts
            for s, e in segs:
                if s in true_starts and (e + 1 in true_starts or e == len(idx) - 1):
                    seg_total += 1
                    post = Posterior.from_prior(model_prior_for("PDF"))
                    post.update("L1", l1.likelihood(d["feats"][[idx[s]]])[0])
                    seg_right += post.top()[0] == to_model_class(d["cls"][idx[s]])
        else:
            n_multi += 1
            false_split += len(segs) > 1
    print(f"\ndev-test boundaries: precision {tp / max(tp + fp, 1):.3f}, recall {tp / max(tp + fn, 1):.3f}")
    print(f"bundles split exactly right: {exact}/{n_bundles}")
    print(f"single multi-page documents wrongly split: {false_split}/{n_multi}")
    print(f"correctly split segments whose top class from layout + prior is right: {seg_right}/{seg_total}")
    print("pair-model weights [cos, js, argmax change, first-page score, shape, area, kind change, scanner change]:",
          np.round(pair_clf.coef_[0], 2).tolist())


def _f1(pred: np.ndarray, y: np.ndarray) -> float:
    tp = np.sum(pred & y)
    return 2 * tp / max(np.sum(pred) + np.sum(y), 1)


if __name__ == "__main__":
    main()
