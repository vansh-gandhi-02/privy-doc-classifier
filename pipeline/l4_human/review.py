"""L4: human review, the last resort (D8, D26, D30).

A document reaches a person when the LLM leaves it below 95% or answers "none
of these". The brief quotes no price, so review is costed from config/budget.yaml
(0 by default) and the number of documents is reported instead.
"""
from __future__ import annotations

from common.config import load

HUMAN_REVIEW = "HUMAN_REVIEW"


def price_inr() -> float:
    """Rupees per document reviewed (config/budget.yaml: human_review_inr_per_doc)."""
    return float(load("budget")["human_review_inr_per_doc"])
