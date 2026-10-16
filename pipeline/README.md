# pipeline/: the classifier

Every document carries a probability for each of the 15 classes (`posterior.py`). It starts from the class mix expected for its file format and never at zero. Each level reads more of the document, at a higher price, and updates the probabilities with Bayes' rule. A document stops as soon as one class reaches the gate (95% by default). Otherwise it moves on to the cheapest next level that can still separate the classes in play.

```
file ─▶ L0 open ─┬─ duplicate? ─▶ copy the first copy's label
                 ├─ trusted text ─▶ L2 text model ─▶ (L1 if still unsure)
                 └─ scan / image ─▶ bundle splitter ─▶ L1 layout ─▶ L2 reading ladder
                                                               │
          KYC ID document? ─▶ address question (PoI or PoA) ◀──┤
                                                               ▼
                                       still below the gate ─▶ L3 LLM ─▶ L4 human
```

| Level | Folder | What it reads | Cost (one laptop core) |
|---|---|---|---|
| L0 | `l0_open/` | Bytes, trusted text, checksum | 2.5 ms per file |
| L1 | `l1_layout/` | A picture of each page (frozen DiT), plus the bundle splitter | 0.11 s per page |
| L2 | `l2_text/` | Free text, or a reading ladder over OCR; the address question | 0.5 s / 2.2 s per read |
| L3 | `l3_llm/` | Masked text, 2-5 candidate classes | about Rs 0.04 per call |
| L4 | `l4_human/` | What is still unsure | No price quoted; counted |

**Files at this level:**
- `posterior.py`: the probabilities, Bayes updates and gates. A merged class (KYC ID document) cannot be accepted until the address question splits it.
- `run.py`: one document's whole path, L0 to the address question. Used by training, evaluation, the lockbox runs and `scripts/classify.py`, so every result comes from the same code.
- `controller.py`: the gates and the budget controller. One gate, tau (85-99%), applies to every step before the LLM. Critical documents never get a gate below 95%.

Each level's folder has its own README. The reasoning behind every choice is in `../DECISIONS.md`.
