# L3: the LLM, only for what L1 and L2 could not settle

About 0.6% of documents reach this level.

**What the LLM sees (`llm.py`):**
- The text already read, with every identifier replaced by its type: `[AADHAAR_VALID]`, `[PAN_PERSON]`, `[CARD_MASKED]`, `[PHONE]`, `[DATE]`, `[PIN]`. The type is still evidence; the value never leaves the machine. Measured on the Maskara Indian PII test set: PAN, DL, email and UPI 100% removed, Aadhaar 88%, phone 85%. Names are not masked yet.
- Only the 2-5 classes still in play (those covering 99% of the probability), each with a one-line definition that carries our labelling rules, plus "none of these" (which goes to a human).

**How its answer is used:** as a sensor with a measured error rate. On calibration documents we count how often it picks the true class when the true class is offered, and how often it says "none". Its answer then updates the probabilities like any other evidence, and the document is accepted at 95%. The LLM is never asked for its own confidence.

**Safety:** the document text is marked as untrusted data; the model runs with all tools switched off; an answer that is not one of the listed letters is rejected.

**How much should it think? Measured** (`scripts/run_l3_compare.py`, 150 hard documents):

| Mode | Accuracy | Rs per call |
|---|---|---|
| Answer only | 0.927 | 0.016 |
| **Quote the deciding words, then answer** (chosen) | 0.987 | 0.038 |
| Full thinking | 0.987 | 0.039 |

The rule, set before the results: the cheapest mode whose accuracy is at least 95% with 90% confidence.

**Backend:** Claude Haiku through `claude -p` on a Claude subscription (tools off, our own short system prompt, run from an empty folder), standing in for the API call a production system would make. Tokens are priced at the brief's rates; the CLI's own overhead (about 630 tokens a call) is subtracted. To run this level on new documents you need the `claude` CLI logged in to your own subscription, or to swap `call()` for an API client with your own key.

Decisions: D11, D25, D28.
