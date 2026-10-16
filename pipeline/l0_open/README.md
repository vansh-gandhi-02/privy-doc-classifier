# L0: open the file (free)

**What it does**, per file, with no model and no OCR:
- Finds the true type from the first bytes, not the file extension.
- Separates trusted text (text visibly drawn on the page) from scans. Invisible OCR layers and text hidden under images are not trusted, because that is where someone could plant words to fool the classifier or the LLM.
- Unpacks emails and zips. An email is classified by its attachment.
- Spots exact duplicates by checksum. A duplicate copies the first copy's label at no cost. Near-duplicates are deliberately not merged: a Class 10 and a Class 12 marksheet can differ by two words.
- Sets the starting probabilities: the assumed class mix for this file format (`config/class_mix.yaml`), never zero.
- Picks the route. Files with trusted text go to the text model first; scans and images go to the layout model first ("cheapest evidence first", D22).

**Cost:** about 2.5 ms per file. Over all 5M files that is under Rs 60, and it also gives exact page counts. So running L0 over the whole bucket first is the cheap way to firm up the cost forecast before a real run.

**Measured (dev sample):** true type right 3,951/3,951; route right 3,197/3,197; 76/76 planted duplicates caught with no false alarms.

**Files:**
- `metadata.py`: `open_file`, the format prior (`prior_for`, `model_prior_for`), and the prior share of Proof of Address among KYC documents (`poa_share`).
- `filetype.py`: true type from the bytes; which PDF pages carry trusted visible text.

Decisions: D19, D22.
