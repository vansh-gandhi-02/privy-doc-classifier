# tools/: deliverables and the cache

| File | What it does |
|---|---|
| `make_flowchart.py` | Writes `deliverables/flowchart.drawio`, with the measured numbers pulled from the metrics files. Every arrow runs through fixed points, so none cross. `flowchart.pdf` is that file printed from the draw.io viewer |
| `make_doc.py` | Writes `deliverables/numbers.tex` from the metrics files and compiles `deliverables/approach.tex` into `approach.pdf`, the two-page approach note (needs [tectonic](https://tectonic-typesetting.github.io) or any XeLaTeX) |
| `artifacts.py` | `pack` copies the slow-to-compute results into `artifacts/`; `unpack` puts them back into `data/` |
