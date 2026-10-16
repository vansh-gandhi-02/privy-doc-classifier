"""Scoring against the brief's bar: macro-F1 >= 0.85 and recall >= 0.90 on critical classes.

Two choices are built in:
- Reweighting (D14): the sample over-represents rare classes on purpose, so each
  document carries a weight that maps the sample back to the assumed bucket mix.
- Abstentions (D8): documents left for human review are labelled ABSTAIN. We
  report macro-F1 both ways, counting them as errors and leaving them out.

"other" is not a scored class, but an "other" document predicted as a real
class counts as a false positive for that class.
"""
from __future__ import annotations

from sklearn.metrics import f1_score, recall_score

ABSTAIN = "ABSTAIN"


def macro_f1(y_true, y_pred, labels, sample_weight=None, abstain: str = "error") -> float:
    """abstain="error": an abstained document is a miss for its true class.
    abstain="exclude": abstained documents are dropped before scoring."""
    if abstain == "exclude":
        keep = [i for i, p in enumerate(y_pred) if p != ABSTAIN]
        y_true = [y_true[i] for i in keep]
        y_pred = [y_pred[i] for i in keep]
        sample_weight = None if sample_weight is None else [sample_weight[i] for i in keep]
    return float(f1_score(y_true, y_pred, labels=labels, average="macro", sample_weight=sample_weight, zero_division=0))


def per_class_recall(y_true, y_pred, labels, sample_weight=None) -> dict[str, float]:
    scores = recall_score(y_true, y_pred, labels=labels, average=None, sample_weight=sample_weight, zero_division=0)
    return dict(zip(labels, map(float, scores)))


def meets_bar(y_true, y_pred, labels, critical, sample_weight=None, macro_min=0.85, recall_min=0.90) -> dict:
    recalls = per_class_recall(y_true, y_pred, labels, sample_weight)
    f1_err = macro_f1(y_true, y_pred, labels, sample_weight, abstain="error")
    return {
        "macro_f1_abstain_as_error": f1_err,
        "macro_f1_abstain_excluded": macro_f1(y_true, y_pred, labels, sample_weight, abstain="exclude"),
        "critical_recall": {c: recalls[c] for c in critical},
        "passes": f1_err >= macro_min and all(recalls[c] >= recall_min for c in critical),
    }
