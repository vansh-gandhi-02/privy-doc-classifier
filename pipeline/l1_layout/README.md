# L1: the page layout, and the bundle splitter

## Layout (`layout.py`)

**What it does:** renders each page small (448 px) and describes it two ways:
- DiT (`microsoft/dit-base-finetuned-rvlcdip`, MIT licence), used frozen: its 768-number summary of the page plus its 16 document-type scores. It was pretrained on millions of real document images, so it is not tied to our generator.
- Six readable signals: page shape, how card-like it is, a QR code, a face, ink density, colour.

A small logistic regression on top gives P(class | page). It is calibrated by temperature scaling, and handed to the posterior with the training class mix divided out, so the mix is not counted twice.

**Why:** about half the bucket has no usable text. And a passbook and a bank statement share their words (customer ID, branch, balance) but not their look; layout separates them without reading anything. Template matching may narrow the bucket but never decides the class, because a Class 10 and a Class 12 marksheet share a template.

**Measured (dev-test):** settles 64% of scanned documents at 100% accuracy; fixes only the bucket for another 28% (always right); 8% go on; cross-bucket mistakes 0.7%. Cost 0.11 s per page on one CPU core (render, signals, DiT on CPU).

## Bundle splitter (`bundles.py`)

**What it does:** real buckets contain merged PDFs. Every page is compared with the one before it: layout similarity, how far apart their class guesses are, whether the new page looks like a first page, and free cues from L0 (size or shape change, digital vs scan, a different scanner). A small model turns these into P(a new document starts here); unsure pages stay with the current document.

**Printed page numbers overrule the layout model (D30).** The splitter reads the page-number line of every page of a multi-page file: trusted text on digital pages, and the top and bottom lines of scanned pages. "Page 3" forbids a cut; "Page 1" forces one.

**Why the page numbers:** on bank statements from another generator (AgamiAI), the layout-only splitter cut each 6-page statement into about 2.5 pieces, because their continuation pages looked unfamiliar. With page numbers, all 80 statements of a fresh dev batch stayed whole, and our own bundles still split as before (29/30 exact, 1/191 single documents split). The sealed Lockbox D result is in the main README.

**Output:** one row per document inside the file, with its page range. Critical recall is counted per document, so an Aadhaar buried in a bundle still has to be found.

Decisions: D20, D21, D30.
