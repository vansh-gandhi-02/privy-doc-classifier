# L4: a person, last

A document reaches a person only when the LLM's answer still leaves it below 95%, or the LLM says "none of these". Its output label is `HUMAN_REVIEW`.

**How many:** about 0.05% of documents, so about 2,600 at 5M. Setting up a real run needs about 600 more: people check the labels of a starting sample only where the LLM and our models disagree. That keeps human work in the low thousands.

**Cost:** the brief quotes no price for human review, so it is costed at zero (`config/budget.yaml`, `human_review_inr_per_doc`) and counted instead. Changing that one number re-prices every report.

**In the prototype** human review is simulated: in the headline scores a `HUMAN_REVIEW` document counts as an error (D8), and the scores are also reported with those documents left out.

`review.py` holds the label and the price.

Decisions: D8, D26, D30.
