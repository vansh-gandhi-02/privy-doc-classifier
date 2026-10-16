# config/: facts and assumptions, kept apart

| File | What it holds | Source |
|---|---|---|
| `brief.yaml` | Facts from the brief only: 5M documents, Rs 1,00,000 cap, the rate card, the format split, the accuracy bar | The brief |
| `classes.yaml` | The 15 classes plus "other", their 7 buckets, which are critical, and the merged "KYC ID document" class the models use (D24) | D4, D7, D24 |
| `subtypes.yaml` | The 45 document sub-types the generator draws, and the class each maps to (e.g. Aadhaar back is Proof of Address) | D3, D6 |
| `class_mix.yaml` | **Assumed:** each class's share of the bucket and its format split; reproduces the brief's format split within 0.03 points | D14 |
| `budget.yaml` | Our targets: Rs 50k compute target, 10% reserve, Rs 60k ceiling; human review price (0: none quoted) | D2, D26, D30 |
| `sample.yaml` | Dev sample size and the train/calibration/dev-test split | D15 |

`python -m scripts.check_mix` checks that the class mix still reproduces the brief's format split after any edit.
