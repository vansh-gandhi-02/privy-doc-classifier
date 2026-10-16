# tools/: deliverables and the cache

| File | What it does |
|---|---|
| `make_flowchart.py` | Writes `deliverables/flowchart.drawio`, with the measured numbers pulled from the metrics files |
| `make_doc.py` | Writes `deliverables/approach.pdf`, the two-page approach note, from the metrics files |
| `artifacts.py` | `pack` copies the slow-to-compute results into `artifacts/`; `unpack` puts them back into `data/` |
