# Decisions and assumptions

This file is the single place for every decision that shapes the prototype. Code and configs refer to these IDs.

Statuses:
- **DECIDED**: Vansh has made the call.
- **ADOPTED**: Claude's proposal, with no objection from Vansh.
- **OPEN**: still needs an answer.

## D1. Passbook vs bank statement: DECIDED (15 Oct)

- Passbooks are kept separate from Bank Statement and labelled `other`. They serve as hard negatives.
- They share header text with statements (customer ID, branch, balance) but differ in layout and format.
- Configured in `config/subtypes.yaml` as `passbook_page`.

## D2. Margin and compute budget: DECIDED (15 Oct)

- **Compute target:** ₹50k (50% margin on compute), revised from ₹40k on 16 Oct (D26). The controller aims at ₹45k, keeping a 10% reserve.
- **Ceiling:** ₹60k (Vansh's 40% floor). Spending above it needs sign-off.
- **Client cap:** ₹1L stays the brief's hard limit.
- **Assumption:** the job runs as a productised Privy job, so delivery labour is 0.
- **Why it's settled:** it changes no pipeline inputs or outputs. It is one number the controller aims for, plus one sentence in the write-up.

## D3. Proof of Identity vs Proof of Address: DECIDED (15 Oct)

KYC is 20% of the bucket: PoI 12%, PoA 8%. Every address document also proves identity, but the brief scores PoI and PoA as two classes. So the labelling rule is:

- **PAN:** always PoI (it has no address).
- **Aadhaar, Driving Licence, Passport, Voter ID:** PoA if an address is visible, otherwise PoI.

**Deviation from the brief.** The brief lists Voter ID only under Proof of Address. We treat it as Proof of Identity too: the front of a Voter ID (photo, name, EPIC number) proves identity and shows no address. RBI's KYC rules list the Voter ID card among their "officially valid documents" (cited from memory; check before quoting).

## D4. Step-1 buckets: DECIDED (15 Oct)

- Seven buckets plus Other, as listed in `config/classes.yaml`.
- These are a hypothesis. They get checked against the confusion matrix of the first cheap model.

## D5. Environment: DECIDED (15 Oct)

- Built locally in a Python 3.12 venv, to match Colab.
- The project folder sits outside the iCloud-synced Documents folder.

## D6. Legal Contract vs Property: DECIDED (15 Oct)

- **Property & Collateral:** anything that transfers, mortgages, titles or values property.
- **Legal Contract:** every other agreement, including rent agreements.

## D7. Critical classes: DECIDED (15 Oct)

**The four critical classes:** Legal Contract, Property & Collateral, Proof of Identity and Proof of Address.

The brief's examples are "legal, regulatory, medical":
- **Medical:** none of the 15 classes is medical.
- **Regulatory:** in a bank this means KYC, which RBI mandates. GST, ITR and company filings are government filings, but the bank is not penalised over them.
- **Legal:** covers both legal contracts and property documents. Sale deeds and titles are legal instruments, and they are the bank's security.

**Consequence:** PoI vs PoA and Legal vs Property are the two pairs most likely to be confused. Both sit entirely inside the critical set, so the D3 and D6 rules need to hold up.

## D8. Abstentions in macro-F1: ADOPTED

- **Headline:** documents sent to human review count as errors.
- **Secondary:** the same score with those documents excluded.

## D9. Per-document probability and thresholds: DECIDED (Vansh's design, 15 Oct)

- Each document starts from a prior, never 0, and its probabilities are updated at each step.
- A document is accepted once one class reaches 95%.
- A bucket can be locked earlier, once the bucket's combined probability reaches the threshold.
- The budget controller moves the threshold at the gate where documents go to the LLM.

## D10. How evidence is combined: ADOPTED

- **Cycle 1:** multiply the likelihoods together.
- **Once labelled data exists:** switch to a calibrated update.

## D11. LLM backend: DECIDED (15 Oct)

- Claude Haiku, called through the Claude Code subscription (`claude -p`).
- Our own tokens are priced at the brief's rates (₹22 per million input, ₹88 per million output).
- **Subtracted:** Claude Code adds about 14.7k harness tokens to every call. We measure that baseline once and subtract it.
- **Reported separately:** thinking tokens.

**"Local intelligence"** means the small models we train ourselves (L1 and L2), which take seconds on a laptop. No LLM is trained or hosted locally.

## D12. EML files: ADOPTED

- An email is classified by its attachment.
- No attachment: Other.
- Several attachments: classified by the first one.

## D13. 15 classes, not 25: ADOPTED

The "25" in the brief is a leftover from another version. Stated as an assumption in the write-up.

## D14. Class mix: DECIDED

- Set in `config/class_mix.yaml`, with KYC at 20%.
- It matches the brief's format split to within 0.03 points.

## D15. Synthetic data: ADOPTED

- Synthetic documents only. No real people's IDs.
- The test set holds out unseen issuers.

**Lockbox A** was built and sealed on 15 Oct at 03:55.
- Location: `data/lockbox_a`.
- Size: 805 files, including 313 in the unseen layout variant 3 and 34 bundles.
- Seal: the SHA-256 of `labels.csv` is `bdf42054e6ed73462149bc7f1d9753dd7c087fe46088138f7dbb817951f33d4f`. Re-hash the file before the final run; a match proves nobody touched the labels.
- What has been read so far: only the summary counts (variant mix and bundle count), to confirm the build. No per-file label has been read or used.
- Rule: the lockbox gets one run, with the frozen pipeline, and the report shows whatever comes out.

## D16. Deadline: DECIDED (15 Oct)

- Submit by 16 Oct.
- At most about 2 more hours of Vansh's time, spent at three review checkpoints.

## D17. Clarifying email: DECIDED (15 Oct)

- No email.
- The assumptions go in a short list in the approach doc.

## D19. Walkthrough step 1 (L0, opening the file): DECIDED (15 Oct)

**Trusted text vs scans**
- Only visible text drawn on top of the page counts as trusted text.
- Invisible OCR layers, and text covered by a full-page image, are untrusted. Pages like that are treated as scans.
- Hidden text is also where someone could plant words to fool the classifier or the LLM.
- Implemented in `pipeline/l0_open/filetype.py`.
- **Exception:** the distrust applies to hidden text in incoming files from unknown sources. OCR text that our own pipeline produced (for example ocrmypdf's searchable-PDF layer) is trusted, because we know where it came from.

**Duplicates**
- Deduplication at L0 uses exact checksums only.
- Near-duplicates are not merged: a Class 10 and a Class 12 marksheet can differ by a couple of words.
- The demo plants duplicates to show they are caught.
- The cost extrapolation assumes 0% duplicates, so any duplicates found are a bonus, not a saving we depend on.

**External test set**
- Lockbox B was planned to include Vansh's own masked documents; he later chose not to use them (D27), so the masking tool was removed. Lockbox B became an outside dataset.
- These documents never go into the repo.

## D20. Walkthrough step 2 (L1, page layout): DECIDED except bundles (15 Oct)

- **Template matching** (nearest known layout) can set the bucket, never the class. A Class 10 and a Class 12 marksheet from the same board share a layout.
- **Scanned PDFs:** about 40% of PDFs are scans. This brings the share of documents with no usable text to about 54%, or 2.7M.
- **Layout model at L1:** a pretrained document vision model (DiT), used frozen. Its page summaries plus three readable signals (page shape, QR code, photo) feed one small classifier. Training takes seconds; summarising the pages takes minutes.
- **OCR reading ladder:** each rung runs only while the document is still below threshold.
  1. Pick the first informative page, skipping near-blank ones.
  2. Read its header (top quarter).
  3. Read the whole page.
  4. Read the next informative page and the last page.
  5. Send it to the LLM.
- **Bundles are not assumed away.** Vansh rejected "one type per file", because real buckets will contain merged PDFs. How to split and score them is OPEN; see the step 2 follow-up.

**Measured OCR cost (15 Oct, RapidOCR, one core of this Mac, dense synthetic page):**

| Read | Core-seconds |
|---|---|
| Header crop | ~3.5 |
| Full A4 page | ~12.7 |
| Selective read: find every box, read only the top 4 lines | ~0.85 |

**Remeasured overnight on real synthetic pages, which are less dense (`costs/timing.py`):**

| Read | Core-seconds per page |
|---|---|
| Selective read | 0.63 |
| Full read | 2.9 |

At 5M documents this means:

| What is read | Cost on this machine | Cost on a cloud vCPU (2x) |
|---|---|---|
| A selective read of every scanned page | ~₹3.7k | ~₹7.4k |
| Each 10% of pages that also need a full read | ~₹1.7k more | ~₹3.4k more |

The D21 figure of +₹7.5k for every extra 10% of full reads was based on the dense worst-case page and is too high.

Finding the text boxes takes under 1 s; reading the lines is the rest, at about 0.2 s per line. So full CPU OCR of every scanned page would break the budget. OCR has to be selective: find all the boxes, but read only a few lines.

## D21. Bundled PDFs: DECIDED (15 Oct)

**How a file is split into documents (option A)**
- Every page gets two pieces of evidence:
  - the L1 layout summary
  - a selective read: every text box found, then only the top lines and the largest-font lines read
- A new document starts only when one of these holds:
  - a page is confidently a different class
  - a page shows a strong "first page" sign: a new title, a new letterhead, or "Page 1 of"
- Unsure pages stay with the current document. Continuation pages have no title.
- Each resulting document is then classified with the reading ladder.

**What the output and scoring look like**
- The output lists every document found in the file, each with its page range, class and confidence.
- The file as a whole takes the class of its first document.
- Critical recall is counted per document, so an Aadhaar buried inside a bundle still has to be found.

**In the demo**
- About 10% of multi-page PDFs are bundles of 2 to 5 documents.
- The true page ranges are recorded, so the accuracy of the split can be measured.

**Cost**

| Item | Estimate |
|---|---|
| Selective reads of all ~5.3M scanned pages | ~₹5k (one core of the Mac) |
| Same work on a cloud vCPU (1.5 to 2x slower) | ~₹7.5k to ₹10k |
| Each extra 10% of pages that need a full read | +~₹7.5k |

## D22. Cheapest evidence first: DECIDED (15 Oct)

Evidence for each document is gathered in order of cost:

- **Files with free text** (digital PDFs, DOCX, XLSX, TXT, email bodies): check the text first. The layout model runs only if the document is still below threshold.
- **Images and scans:** layout first, then the reading ladder.
- **Choosing the next step:** whenever a document is unsure, the next step is the cheapest one that can tell its remaining candidate classes apart (the discriminator table). For example, a statement-vs-passbook doubt goes to the layout model, but a loan-vs-card-application doubt goes to text.

So the stages are not a fixed L1 → L2 order. The flowchart has to show this routing.

## D23. Walkthrough step 3 (L2, text): DECIDED (16 Oct)

**3a. The text model**
- Learned word weights: 3-5 letter pieces of words, fed to a logistic regression. Trains in seconds, survives OCR typos, and the weights can be printed.
- A small transformer fine-tuned with LoRA is the **next upgrade**, stated in the write-up. It needs a labelled corpus and its own evaluations, which a take-home can't supply.

**3b. ID numbers are evidence, not verdicts**
- A word or ID counts only if it is more common under one remaining candidate than another. Shared words (customer ID, branch, balance) cancel out.
- Three levels per ID: valid checksum, pattern only (likely an OCR typo), none.
- Context features: which ID types appear, how many, and IDs per line. A card has one ID in 10-15 lines; a form has 3-4 among 100+.
- IDs enter the same text model as extra inputs, not as hand-set multipliers, so their weights are learned and calibrated with the words.
- To add: UDIN (audit reports) and CIN (company documents).

**3c. One model over all classes**
- One softmax model answers "which class is this?" and its outputs add up to 1. Not one yes/no model per class: those don't add up, and none of them learns a specific pair such as PoI vs PoA.
- The odds between any two classes come from the gap between their weight rows, so the discriminator table for every pair falls out of the same model.
- Before each update, the model's output is divided by its training class mix, so the prior isn't counted twice.
- Narrowing to the classes still in play sets the others to 0 and rescales; ratios among the rest don't change.
- The specialist per bucket is a reading recipe (where on the page to read), not a separate model.

**Generator fix (option B, chosen by Vansh)**
- The old generator printed the full Aadhaar number only on KYC cards and the masked one only on forms, so a model could learn "full Aadhaar = KYC card". Deeds printed no PAN.
- Now: Aadhaar cards and e-Aadhaar letters print masked numbers 30% of the time; forms and ITRs 50%; registered deeds (and 30% of unregistered ones) quote the parties' PAN, and often Aadhaar. All shares are assumptions.
- Both practices are from memory and need checking before quoting: UIDAI's masked Aadhaar download, and Income Tax Rule 114B (PAN on property deals above ₹10 lakh).
- The dev sample was rebuilt. **Lockbox A was not rebuilt**, so it still carries the old shortcut; this is stated as a limitation of the Lockbox A result.

## D24. Proof of Address as a sub-question of KYC: DECIDED (Vansh, 16 Oct)

- The type models (L1, L2) choose among 15 options: PoI and PoA merge into one "KYC ID document" class.
- Every document that lands in KYC gets one more question: **"is an address visible?"** Yes gives PoA, no gives PoI. This is the D3 rule applied directly.
- The output is still the brief's 15 classes plus other. P(PoA) = P(KYC) × P(address); P(PoI) = P(KYC) × (1 − P(address)). The probabilities still add up to 1.
- **Why:** PoI vs PoA is not a document type (an Aadhaar front and back are one document); it depends on one property. Checking that property should carry over to unseen card designs better than learning the look of each card side. "PAN is always PoI" and "both sides on one scan" need no special rules.
- **Address, defined:** an address label or address-shaped block, plus a valid PIN code, plus a state name. "Place of Birth: PUNE, MAHARASHTRA" on a passport data page is not an address.
- **Assumption:** the brief's PoA list is all ID documents (Aadhaar, DL, Passport, Voter ID), so PoA sits inside the ID documents. Utility bills are labelled `other`. If a client counted them as PoA, this would need revisiting.
- **How the question is answered: option A, DECIDED (Vansh, 16 Oct).** Every KYC document gets a full read (or its free text) for the address question; layout is not used as a shortcut. Reason: these are critical classes, the cost is bounded, and the decision stays on the rule itself rather than on how a card side looks.
- **Accepting:** a KYC document is accepted only when P(KYC) × P(address) (or × (1 − P(address))) reaches 95%. Until the address question has been asked, "KYC ID document" can only lock the KYC bucket, never be accepted.
- **Applied to the earlier steps:** L1 and the bundle splitter were retrained on the 15 model classes (results in the README and the notebook).

**Step 3 is closed (16 Oct).** Built: `pipeline/l2_text/features.py`, `pipeline/l2_text/address.py`, `pipeline/l2_text/text_model.py`, `scripts/extract_text.py`, `scripts/train_l2.py`.

One implementation detail differs from the 3c wording: when a bucket is locked, L2 still updates all 15 classes rather than zeroing the ones outside the bucket. The ratios among the classes in play come out the same, and a wrong bucket lock can still be undone by the text. Restricting to the candidates is kept for the LLM prompt (step 4).

## D25. Walkthrough step 4 (L3, the LLM): 4a-4c DECIDED, 4d OPEN (16 Oct)

**Backend (D11, confirmed):** the Claude Code subscription via `claude -p`, not API billing. `claude -p` stands in for the API call a production system would make.

**Measured setup (16 Oct):**
- Each call runs as `claude -p --model haiku --tools "" --system-prompt <ours> --strict-mcp-config --setting-sources "" --no-session-persistence --output-format json`, from an empty folder.
- With tools off and our own system prompt, the harness overhead is about 630 tokens per call, not the ~14.7k in D11. It is still measured and subtracted.
- Thinking tokens are reported separately by the CLI (`output_tokens_details.thinking_tokens`).
- Thinking control: `MAX_THINKING_TOKENS=0` turns it off; the default thinks adaptively (0-100 tokens on an easy question); `--effort max` thought for ~530 tokens on the same easy question.
- Latency: about 1.5-3 s per call.

**4a. What the LLM sees:** the text already read (full page, plus later pages if read), with each ID replaced by its type (`[AADHAAR_VALID]`, `[PAN_PERSON]`, `[PIN]`) so the type stays as evidence and the value never leaves the machine. Names are not masked (limitation). Document text is marked as untrusted data; the answer must be one of the listed options or it is rejected; tools are disabled.

**4b. Choices offered:** the smallest set of classes covering 99% of the probability (2 to 5), each with a one-line definition (D3, D6), plus "none of these", which goes to L4.

**4c. How the answer is used:** the LLM is a sensor with a measured confusion matrix: P(LLM says j | true class i), counted on calibration documents that would have escalated. Its answer updates the posterior like any other evidence. The LLM is not asked for its own percentage.

**4d. Reasoning length: OPEN.** Vansh's view: Haiku without thinking will struggle where L1 and L2 did, and thinking might reach ~95% and avoid a further step. To be decided by measurement: label only, quote-then-label, and thinking at `--effort max`, on a hard set from calib and dev-test.

## D26. Walkthrough steps 5-9, speedrun: DECIDED (Vansh, 16 Oct)

- **Step 5, L4 human review:** documents still under 95% after L3, plus "none of these" answers. Simulated, priced at ₹1 per document (budget.yaml, UNVERIFIED). Every rupee figure in this project is a benchmark of what the job would cost; nothing is spent. Vansh expects L4 to stay at or under 1% of documents; the share reaching L3 (~3% on partial data) is not the share reaching humans.
- **Step 6, gates:** accept at 95%. The controller moves only the L2 -> L3 gate, **between 85% and 99%** (Vansh raised the floor from 80%). Critical safety net: a document with at least a 10% chance of a critical class keeps a 95% gate.
- **Step 7, budget controller:** **target ₹50k with a 10% reserve**, so the controller aims at ₹45k (a 50% margin on compute; this revises D2's ₹40k). The ceiling stays ₹60k. Demo: a simulated 5M run with a scan-heavy stretch mid-run.
- **Step 8, setup:** no people are needed for the prototype. For a real run, a seed of labelled real documents is still needed, because the models learned from synthetic data. Proposed: the LLM labels a random sample, and people check only where it disagrees with L1 and L2. This is a one-off cost line in the write-up, not spend.
- **Step 9, evaluation:** dev-test scored; Lockbox A run once (`scripts/run_final.py`); brute-force baseline calculated from measured timings (`costs/baseline.py`) instead of an ocrmypdf run. Lockbox B became an outside dataset (D27).

## D27. External data, Lockbox B and delivery: DECIDED (16 Oct)

- **Vansh's own documents: not used.** He was not comfortable masking them. He will check the generated documents by eye instead (`data/sample/contact_sheet.jpg`).
- **Lockbox B = 120 statements from AgamiAI/Indian-Bank-Statements** (Hugging Face, Apache 2.0, fully synthetic, made by a different generator than ours). 30 from each of its four folders: digital and scanned, two layouts each, 718 pages in all. Everything in it is a bank statement, so it measures recall on one class from an outside source, not precision. Sealed on 16 Oct: SHA-256 of `data/lockbox_b/labels.csv` is `fa6ae7f7067e152dd4b190ad3cc6ef5e44d18c40afa1bb87f4f24c0999eb5289`. One run, with the frozen pipeline, like Lockbox A.
- **somukandula/maskara-indian-pii-200k** (MIT, synthetic short texts with labelled Indian PII spans): not documents, so not a classification test. Used to measure how much PII the L3 masker removes, by type. One preview row reads like an instruction ("Check the latest commit in the repository."); it is a data value and was not acted on.
- **KanoonGPT/indian-legal-documents:** skipped. It is mostly Acts, Rules and Notifications, not contracts or deeds, so it does not test the legal or property classes.
- **Delivery** (revised by Vansh, 16 Oct): a GitHub repo with a notebook that runs locally (no Colab). The notebook replays the cached LLM answers, says so, and is committed already run so the outputs show on GitHub. Nothing is pushed until Vansh does it.
- **Rule from Vansh:** no API calls and no billing. LLM calls only through `claude -p` on the subscription.

## D28. Findings from the final build: ADOPTED (16 Oct, overnight)

**L3 mode (closes D25 4d): quote-then-label** (thinking on the first run; see the final re-run below). 450 `claude -p` calls (subscription only) on 150 hard calib and dev-test documents:

| Mode | Hard-set accuracy | Calib half (66) | Rs per call | Thinking tokens |
|---|---|---|---|---|
| Label only | 0.927 | 0.955 (63/66) | 0.016 | ~3 |
| Quote, then label | 0.987 | 1.000 | 0.040 | ~190 (it thinks despite the switch) |
| Thinking, max effort | 0.987 | 1.000 | 0.041 | ~290 |

The rule as first written (cheapest mode at 95% or more on calib) picked label-only by one document. On 66 documents that estimate is noisy, so the rule now asks for the **lower 90% Wilson bound** to clear 95%: label-only 0.89 fails, thinking 0.96 passes. At 5M the difference is about Rs 450 in total, because only ~18k documents reach the LLM. This matches Vansh's view that plain Haiku struggles where L1 and L2 did.

**Final re-run (16 Oct; the run behind the published numbers).** Label only 0.913 at Rs 0.014 a call; quote-then-label 0.987 at Rs 0.038; thinking 0.987 at Rs 0.039. Quote and thinking both clear the bound (0.96); the rule takes the cheaper, so the final mode is quote-then-label. These are the numbers in the notebook, the approach note and the flowchart.

**A stricter 99% gate for critical classes: tested, not adopted.** It sent 65 more dev-test documents (7.7%) to the LLM and fixed none of the errors, because the critical-class errors were confident ones (above 99%).

**Those errors had one cause, now fixed.** Indian contracts and deeds open with an e-stamp certificate page that both share (the passbook problem again); the selective read stopped there. The 3c reading recipe ("legal and property: the deciding words are on later pages") had not been implemented. It now is: documents whose leading bucket is legal/property read the first, next and last pages before L2 decides (`pipeline/run.py`, RECIPES).

**ID feature fix.** A masked card number ("XXXX XXXX XXXX 1234") was counted as a masked Aadhaar. It is now its own feature (`card_masked`).

**Masker fix (L3, 4a).** Measured on the Maskara Indian PII real-world test texts (2,600). Formats that slipped through at first: hyphens, +91 and landline phones, lower-case and spaced PANs, 4-4-4-4 card numbers, old-style DL numbers, dates and UPI IDs. After the fix, the share of PII spans removed: PAN, driving licence, email and UPI 100%, vehicle registration 98%, Aadhaar 88%, phone 85%, date of birth 63%. Names 0% and street addresses partly (only the PIN is masked): stated as a limitation, next step a name model. Classification cues (loan amount, assessment year, statement period, IFSC) survive. The 450 comparison calls used the masker before the last of these fixes; the lockbox runs use the final one.

## D29. Lockbox C and cost precision: DECIDED (16 Oct, ~01:00)

**Lockbox C** (asked for by Vansh): a smaller fresh set from the final generator (after the D23 fix), new seed 31337, 394 files including 17 bundles and 8 exact duplicates, 40% in the unseen layout variant 3. Built after every model, rule and threshold was frozen; sealed at build (SHA-256 of labels.csv `c83a4cc095cdabd86230e06cc072407528092e303c9b093bbccea5c0fe904183`); run once with `scripts/run_final.py`. Result: macro-F1 0.982 with human review counted as errors, critical recall 1.000 on all four, unseen-layout accuracy 0.978. Passes the bar.

**What "never seen" means for the lockboxes.** No lockbox label was used to train, tune, calibrate or choose anything; labels are read only to score the single run. Lockbox A's files were processed (page features, OCR) before the final models existed, which uses no labels. All lockboxes come from the same generator family as the training data (same 45 templates), so "unseen" means unseen files and, for 40%, an unseen layout; Lockbox B is the only set from a different source.

**Duplicates in the final runner** are now found by checksum, as L0 does, and scored with the label copied from their original (Lockbox A had skipped them using the label file).

**Cost precision** (asked for: "accurate to within 1%"). Measured inputs get a 95% interval (`costs/precision.py`): a fresh single-core timing sample, per-document rates resampled within class, LLM cost from token counts. Assumptions that nothing here can measure (cloud vCPU speed, pages per PDF, human price) are shown as a sensitivity table; they move the total far more than 1%. Running the notebook on a cloud vCPU replaces the largest assumption with a measurement.

## D30. Splitter page numbers, cost assumptions, human review: DECIDED (16 Oct, night)

**The splitter fix.** Vansh's rule: test the pipeline on fresh, unfamiliar multi-page files; if it is not good enough, develop the fix on unused AgamiAI statements and test it once on a fresh, unused batch.
- Fresh test (80 unused AgamiAI statements, `data/agami_dev`): the layout-only splitter cut each into 2.5 pieces; only 16/80 kept whole. Not good enough.
- Fix: read the page-number line of every page of a multi-page file (trusted text on digital pages; the top and bottom lines of scanned pages, `pipeline/l2_text/ocr.py` page_cue_read). A printed "Page 3" forbids a cut there; "Page 1" forces one (`pipeline/l1_layout/bundles.py`).
- On the dev batch: 80/80 kept whole (1.0 pieces per file). On our own dev-test files: no change (29/30 bundles exact, 1/191 single documents split).
- Final check: Lockbox D, 120 more unused AgamiAI statements, sealed before the run (SHA-256 of labels.csv `d674d69853b77867174c24fbb134cd6a523761de45e2fae72f1b687f2aaece52`), run once with the full pipeline including the LLM. **Result: all 120 statements kept whole (Lockbox B before the fix: about 2.5 pieces each); 114/120 (95%) labelled bank statement in the end; 22 settled by the LLM, 4 sent to a person, 2 wrong.** Shipped with the fix. The first scoring attempt crashed on a type error in a new reporting line before any result was printed or saved; the line was fixed and the same frozen pipeline re-scored once (the LLM was asked again, 26 calls). Lockboxes A and C were scored before this fix; their numbers stand as they are.
- Cost: one page-number read on every scanned page of a multi-page file, measured and added to the cost model.

**Pages per PDF.** The brief's 350 KB typical PDF implies 1.7 to 6.2 pages depending on scan compression (our scans are about 110 KB a page, AgamiAI's about 476 KB; digital pages about 20 KB). 3 pages stays the central assumption; the range is in the sensitivity table. Before a real run, L0 over the whole bucket (about Rs 225 including storage reads) gives exact page counts.

**Human review** (Vansh): the brief quotes no price, so it is costed at zero, but the count must stay in the low thousands across all stages (seed labelling checks plus L4): about 600 + 2,600.

**Pilot run** (Vansh): at most 10k documents, and only if needed. Not needed: the L0 pass gives page counts and timing the first ~1,000 documents on the real machine gives the cloud speed.

## D18. Cuts for the deadline: ADOPTED

| Instead of | We do | Stated as |
|---|---|---|
| 3 template modules per sub-type | 1 template per sub-type, varied by issuer style; the test set holds out issuers | a limitation |
| A small vision network at L1 | Image features plus logistic regression | a limitation |
| Sending images to the LLM | Sending the text extracted by OCR (masked) | a limitation |
| Conformal prediction for critical recall | A lower escalation bar for documents that might be critical | a limitation |
| A Colab notebook | A repo with a README | a limitation |
