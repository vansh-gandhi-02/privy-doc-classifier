# costs/: what it costs, and how sure we are

| File | What it does |
|---|---|
| `timing.py` | Measures each step's CPU time on one core (selective read, full read, page-number read, L1) and writes `data/bench.json` |
| `precision.py` | The 5M estimate with a 95% interval from what was measured, and a table of how far each unmeasurable assumption moves it |
| `baseline.py` | The brute-force comparison: OCR every page and send every document to the LLM |

Prices come from the brief's rate card (`config/brief.yaml`): Rs 32 an hour for an 8-vCPU machine, Rs 22 and Rs 88 per million LLM input and output tokens, Rs 0.033 per 1,000 storage reads. A cloud vCPU is assumed to be 2x slower than the laptop core measured; pages per PDF are assumed to be 3. Both assumptions are in the sensitivity table, and both disappear with an L0 pass over the real bucket plus timing the first ~1,000 documents on the real machine.
