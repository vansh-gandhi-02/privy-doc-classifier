# docgen/: the synthetic document generator

There are no real customer documents to test on (and there should not be), so this generates them.

- **45 sub-types** (`config/subtypes.yaml`): Aadhaar front and back, e-Aadhaar letter, PAN, passport data and address pages, DL and Voter ID front and back, bank statements, passbooks, card statements, loan and card applications, salary slips, ITR and ITR-V, GST certificates and returns, audited financials, MOA/AOA, board resolutions, contracts, rent agreements, sale and mortgage deeds, valuation and title reports, Class 10 and 12 marksheets, and look-alikes that belong to "other" (utility bills, cheques, passbooks).
- **4 layout variants** of each (`templates/`), varied by issuer style. Variant 3 appears only in the lockboxes, so they test layouts never seen in training.
- **Rendered as real files** (`render.py`, `degrade.py`): digital PDFs, scans (skew, noise, JPEG artefacts), phone photos, screenshots, DOCX, XLSX, PPTX, TXT, emails with attachments, zips.
- **Deliberate traps:** merged bundles (about 10% of multi-page PDFs), exact duplicates, Aadhaar numbers both full and masked on cards and on forms, PAN on deeds, look-alike documents.
- **Fake data** (`fake.py`) with valid checksums (Aadhaar Verhoeff, GSTIN, MRZ) and Indian names, addresses and PIN codes.

`plan.py` sets how many files of each class and format (the class mix, with a minimum per class so rare classes can be scored). `build_sample.py` writes the files, `labels.csv`, `manifest.csv` and a contact sheet:

```
python -m docgen.build_sample                    # dev sample: 4,027 files, ~5 min
python -m docgen.build_sample --run lockbox_c    # a sealed lockbox (refuses to rebuild one already opened)
```
