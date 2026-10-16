# L2: read the text, as little as possible

## The reading ladder (`ocr.py`)

Finding the text boxes on a page is cheap; reading each line is what costs. So scans climb a ladder, and stop as soon as they are sure:

1. **Selective read:** find all text boxes, read only the top lines and the largest lines in the top 40% of the page (titles are big and near the top). About 0.5 s per page.
2. **Full page read.** About 2.2 s per page.
3. **The next informative page and the last page** (blank pages are skipped).
4. Then the LLM (L3).

Each rung replaces the last rung's text evidence instead of adding to it: a full read contains the selective read's lines, so counting both would double count. Files with trusted text skip the ladder; their text is free.

**Reading recipes per bucket.** Indian contracts and deeds open with an e-stamp certificate page that both share, so the legal/property bucket reads its first, next and last pages before deciding. This fixed the only critical-class mistakes on dev-test.

`ocr.py` also has the bundle splitter's page-number read (the top and bottom lines of a page).

## The text model (`features.py`, `text_model.py`)

- **Letter pieces:** the text is lower-cased, digits become 0, and everything but letters and digits is dropped, so "Senior Secondary", "SENIOR SECONDARY" and OCR's "SENIORSECONDARY" all give the same 3-5 letter pieces. They survive OCR typos too.
- **ID evidence:** Aadhaar (Verhoeff checksum), PAN (and whether it belongs to a person or a company), GSTIN (checksum), passport MRZ (check digits), IFSC, Voter ID, DL, UDIN, CIN, PIN codes; each counted as checksum-valid or pattern-only, plus how many ID types appear and IDs per line. IDs are evidence, not verdicts: an Aadhaar number also appears on loan forms and deeds.
- **One model over all 15 classes** (multinomial logistic regression), so the probabilities add up to 1. The gap between two classes' weight rows is the "discriminator table" for that pair: shared words weigh the same in both and cancel (the interviewer's passbook point). Loan vs card application comes down to "loan" vs "card"; Class 10 vs 12 to "secondary" vs "senior".
- **Calibrated per reading depth:** one temperature for free text, selective reads, full reads and multi-page reads, because they carry different amounts of evidence.

## The address question (`address.py`)

PoI and PoA are not different document types; an Aadhaar front and back are one card. So L1 and L2 only decide "KYC ID document", and every KYC document then gets a full read and one question: is an address visible? A valid PIN code plus an address label ("Address", S/O, C/O) or a state name means PoA; otherwise PoI. "Place of Birth: PUNE, MAHARASHTRA" on a passport is not an address: it has no PIN.

**Measured (dev-test):** text alone, accuracy 0.92 from a selective read, 0.98 from a full read, 1.00 from free text. After L1 and L2, 99.5% of documents are settled at 0.999 accuracy; PoI and PoA recall 1.00 on 135 KYC documents.

Decisions: D20, D22, D23, D24, D28.
