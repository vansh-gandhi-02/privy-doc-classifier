# scripts/: build, train, evaluate, run

All run from the repo root as `python -m scripts.<name>`. `run_all` runs the whole sequence.

**Run everything**
| Script | What it does |
|---|---|
| `run_all.py` | Everything in order: from the cached artifacts (~10-15 min) or `--full` from scratch (~2 h) |
| `classify.py` | Classify any folder of documents end to end, no labels needed |

**Build the evidence (slow, cached in `artifacts/`)**
| Script | What it does |
|---|---|
| `run_l0.py` | L0 over the dev sample, with checks (types, routes, duplicates) |
| `extract_pages.py` | DiT features for every page (~6 min) |
| `extract_text.py` | The reading ladder's text for every document (~1 h on 6 cores, resumable) |

**Train and calibrate (seconds to minutes)**
| Script | What it does |
|---|---|
| `train_l1.py` | L1 layout classifier |
| `train_bundles.py` | The bundle splitter |
| `train_l2.py` | The text model and the address question; runs L0 to L2 on calibration and dev-test |

**Evaluate**
| Script | What it does |
|---|---|
| `run_l3_compare.py` | Three ways of asking the LLM, on 150 hard documents (cached answers) |
| `trace_document.py` | Five example documents, their class probabilities after every step (a chart) |
| `run_controller_demo.py` | The budget controller on a simulated 5M run (and `23000` for a squeezed budget) |
| `eval_splitter.py` | The splitter with and without page numbers (D30) |
| `report_bar.py` | The brief's bar per class: precision, recall, F1 on dev-test and the lockboxes |
| `check_masker.py` | How much PII the LLM masker removes (Maskara Indian PII test set) |
| `run_final.py` | A sealed lockbox, run once (checks the seal; refuses a second run) |
| `live_demo.py` | Generate a few fresh documents and run them end to end |

**Small checks used by the tests**
| Script | What it does |
|---|---|
| `check_mix.py` | The assumed class mix reproduces the brief's format split |
| `passbook_walkthrough.py` | The interviewer's passbook example, worked through with the probabilities |
