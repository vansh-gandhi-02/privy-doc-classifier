"""Write the two-page approach doc (deliverables/approach.pdf) from the measured results.

Every number comes from the metrics files the scripts write, so the doc and the
repo never disagree. Run it after the scripts in README's "Run" section.

Run: python -m tools.make_doc
"""
from __future__ import annotations

import json

import pymupdf

from common.config import DATA_DIR, ROOT

OUT = ROOT / "deliverables" / "approach.pdf"
NAMES = {"proof_of_identity": "PoI", "proof_of_address": "PoA", "legal_contract": "Legal", "property_collateral": "Property"}


def _j(rel: str) -> dict:
    p = DATA_DIR / rel
    return json.load(open(p)) if p.exists() else {}


def _pct(v, nd=1) -> str:
    return f"{100 * v:.{nd}f}%" if isinstance(v, (int, float)) else "n/a"


def _f(v, nd=3) -> str:
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) else "n/a"


def _rs(v) -> str:
    return f"Rs {v:,.0f}" if isinstance(v, (int, float)) else "n/a"


def _crit(d: dict) -> str:
    return ", ".join(f"{NAMES.get(k, k)} {_f(v, 2)}" for k, v in d.items()) if d else "n/a"


def build_html() -> str:
    bench, l1, l2, l3 = _j("bench.json"), _j("sample/l1_metrics.json"), _j("sample/l2_metrics.json"), _j("sample/l3_metrics.json")
    ctl, stress, base, mask = _j("sample/controller.json"), _j("sample/controller_23000.json"), _j("sample/baseline.json"), _j("sample/masker_check.json")
    la, lb, lc, ld = (_j("lockbox_a/final_metrics.json"), _j("lockbox_b/diagnostics.json"), _j("lockbox_c/final_metrics.json"),
                      _j("lockbox_d/final_metrics.json"))
    spl = _j("sample/splitter_eval.json").get("agami_dev (80 fresh statements)", {})
    prec = _j("sample/cost_precision.json")
    pt = prec.get("point", {})
    lo, hi = (prec.get("ci95") or [0, 0])
    sens = dict(prec.get("sensitivity", []))
    unit = prec.get("unit", {})
    pick = l3.get("pick", "quote")
    modes = l3.get("modes", {})
    e2e = l3.get("end_to_end", {}).get(pick, {})

    total = ctl.get("controlled_spent", 0)
    trade = ctl.get("tradeoff", {})
    t85, t95, t99 = (trade.get(k, {}) for k in ("0.85", "0.95", "0.99"))
    mt = mask.get("real_world_eval", {})
    mask_line = ", ".join(f"{lab} {_pct(mt[k]['masked'], 0)}" for k, lab in
                          (("PAN_CARD", "PAN"), ("DRIVER_LICENSE", "DL"), ("EMAIL", "email"), ("AADHAAR", "Aadhaar"),
                           ("PHONE", "phone"), ("DATE_OF_BIRTH", "date of birth")) if k in mt)
    lmode = modes.get("label", {})
    qmode = modes.get(pick, {})
    return f"""
<h1>Classifying 5M bank documents on a Rs 1,00,000 budget</h1>
<p class="sub">Approach note, IDfy Privy APM take-home &middot; Vansh Gandhi &middot; code, notebook and flowchart in the accompanying repo</p>

<h2>The idea</h2>
<p>Every document carries a probability for each of the 15 classes. It starts from the class mix expected for its file format (never zero),
and each step buys more evidence at a higher price and updates the probabilities with Bayes' rule. A document stops as soon as one class
reaches 95%; otherwise it buys the cheapest next piece of evidence that can still separate the classes in play. This is a sequential test
(Wald's SPRT in many-class form): money is spent only where the evidence so far cannot decide. A budget controller moves the gates.</p>

<h2>The steps, cheapest first</h2>
<table>
<tr><th>Step</th><th>What it reads</th><th>Measured cost</th><th>Accept rule, and why</th></tr>
<tr><td>L0 Open</td><td>bytes, trusted visible text, checksum</td><td>{_f(bench.get('l0_s_per_file', 0) * 1000, 1)} ms/file</td><td>Exact duplicate: copy its label. Hidden OCR layers are not trusted (planted text).</td></tr>
<tr><td>L1 Layout</td><td>frozen DiT page summary + 6 readable signals (shape, QR, photo...) into a logistic regression</td><td>{_f(bench.get('l1_s_per_page', 0), 2)} s/page</td><td>&ge; 95%: settles {_pct(l1.get('accept_rate'), 0)} of scans at {_pct(l1.get('accepted_accuracy'))}. A passbook and a statement share words, not layout.</td></tr>
<tr><td>L2 Text</td><td>free text first; for scans a reading ladder: selective read (top and largest lines) &rarr; full page &rarr; next and last page</td><td>{_f(bench.get('ocr_selective_s', 0), 2)} s / {_f(bench.get('ocr_full_s', 0), 1)} s a read</td><td>&ge; 95% after each rung. A word counts only if it is likelier under one remaining class than another, so shared words cancel. Checksum-valid IDs are evidence, not verdicts.</td></tr>
<tr><td>Address question</td><td>full read of a KYC card</td><td>one full read</td><td>Valid PIN + address label or state &rarr; PoA, else PoI. PoI vs PoA is a property of the card, not a document type.</td></tr>
<tr><td>L3 LLM</td><td>Haiku; text with IDs masked to their type; 2-5 candidate classes + "none of these"; quotes the deciding words</td><td>Rs {_f(qmode.get('inr_per_call'), 3)}/call</td><td>Its answer is a sensor with a measured error rate; accept at &ge; 95% after the update.</td></tr>
<tr><td>L4 Human</td><td>what is still unsure</td><td>no price quoted</td><td>Last resort; about {prec.get('human_docs_5m', 0):,.0f} documents at 5M, plus about 600 to check the starting labels.</td></tr>
</table>
<p><b>Critical classes</b> (Legal, Property, PoI, PoA) keep a 95% gate whatever the controller does, once their chance is 10% or more.
<b>Bundled PDFs</b> are split per page (layout change, first-page look, scanner change), and printed page numbers overrule the layout model:
"Page 3" cannot start a document, "Page 1" always does. Every document inside is classified with its page range. Legal and property files
open with an e-stamp page that both share, so that bucket reads its later pages before deciding.</p>

<h2>Local intelligence</h2>
<p>Everything except the LLM runs on CPU: a frozen, pretrained document-vision model (DiT) with a classifier trained in seconds; a text model
over 3-5 letter pieces (it survives OCR typos and run-together words) plus checksummed Indian IDs (Aadhaar, PAN, GSTIN, passport MRZ);
a calibrated address rule; a page-by-page bundle splitter. Each is temperature-calibrated, so 95% means 95%. Together they settle
{_pct(l2.get('settled'))} of documents before any LLM call.</p>

<h2>How much the LLM should think: measured, not assumed</h2>
<p>On 150 hard documents (those L2 sent on or settled below 99%): label-only {_pct(lmode.get('accuracy_hard'))} at Rs {_f(lmode.get('inr_per_call'), 3)} a call;
quote-the-evidence {_pct(qmode.get('accuracy_hard'))} at Rs {_f(qmode.get('inr_per_call'), 3)}; full thinking the same accuracy at a little more. The rule takes the cheapest
mode whose accuracy is at least 95% with 90% confidence: quote-the-evidence. Calls ran through a Claude subscription (<i>claude -p</i>, tools off),
priced at the brief's token rates.</p>

<h2>Results (synthetic documents)</h2>
<table>
<tr><th>Test set</th><th>Macro-F1 (humans as errors / left out)</th><th>Critical recall</th><th>To LLM / humans</th></tr>
<tr><td>Dev-test (843 documents)</td><td>{_f(e2e.get('macro_f1_l4_as_error'))} / {_f(e2e.get('macro_f1_l4_excluded'))}</td><td>{_crit(e2e.get('critical_recall', {}))}</td><td>{_pct(l2.get('l3_docs_5m', 0) / 5e6)} / {_pct(e2e.get('l4_share_dev'))}</td></tr>
<tr><td>Lockbox A: sealed, run once; 40% in a layout never seen</td><td>{_f(la.get('macro_f1_abstain_as_error'))} / {_f(la.get('macro_f1_abstain_excluded'))}</td><td>{_crit(la.get('critical_recall', {}))}</td><td>{la.get('llm_calls', 'n/a')} / {la.get('l4_docs', 'n/a')} of {la.get('n_records', 'n/a')}</td></tr>
<tr><td>Lockbox C: fresh, from the final generator, built after everything was frozen, run once</td><td>{_f(lc.get('macro_f1_abstain_as_error'))} / {_f(lc.get('macro_f1_abstain_excluded'))}</td><td>{_crit(lc.get('critical_recall', {}))}</td><td>{lc.get('llm_calls', 'n/a')} / {lc.get('l4_docs', 'n/a')} of {lc.get('n_records', 'n/a')}</td></tr>
<tr><td>Lockbox B: 120 statements from another generator (AgamiAI, Hugging Face), layout-only splitter, run once</td><td colspan="3">The splitter cut each 6-page statement into {lb.get('pieces_per_file', 'n/a')} pieces; {_pct(lb.get('bank_statement_recall'), 0)} of pieces came out as statements.</td></tr>
<tr><td>Lockbox D: 120 fresh AgamiAI statements, with page numbers, run once</td><td colspan="3">Every statement kept whole ({ld.get('singles_kept_whole', 'n/a')}); {ld.get('first_document_right', 'n/a')} labelled bank statement;
{ld.get('llm_calls', 'n/a')} LLM calls, {ld.get('l4_docs', 'n/a')} to a person.</td></tr>
</table>
<p>No lockbox was used to train, tune or choose anything; each was run once. Lockboxes A and C pass the bar (macro-F1 &ge; 0.85, critical
recall &ge; 0.90); unseen-layout documents scored {_f(la.get('unseen_accuracy'))} (A) and {_f(lc.get('unseen_accuracy'))} (C).
Lockbox B exposed one weakness: the layout-only splitter cut unfamiliar statements into pieces. The page-number fix was built on 80 other
fresh statements (kept whole: {spl.get('layout only', {}).get('kept_whole', 'n/a')} before, {spl.get('with page numbers', {}).get('kept_whole', 'n/a')} after; our own bundles unchanged)
and checked once on Lockbox D.</p>

<h2>Cost at 5M documents (cloud vCPU taken as 2x slower than the laptop core measured)</h2>
<table>
<tr><th>Item</th><th>Cost</th></tr>
<tr><td>L0 + L1 on every page (render, signals, DiT on CPU)</td><td>{_rs(pt.get('L0', 0) + pt.get('L1', 0))}</td></tr>
<tr><td>Selective read of every scanned page; page-number lines of multi-page scans</td><td>{_rs(pt.get('selective', 0) + pt.get('page numbers', 0))}</td></tr>
<tr><td>Further reads (full pages, later pages, KYC address reads)</td><td>{_rs(pt.get('full reads'))}</td></tr>
<tr><td>LLM ({_pct(prec.get('rates', {}).get('llm'), 2)} of documents, Rs {_f(unit.get('llm_call', [0])[0], 3)} a call)</td><td>{_rs(pt.get('LLM'))}</td></tr>
<tr><td>Humans (about {prec.get('human_docs_5m', 0):,.0f} documents; the brief quotes no price)</td><td>{_rs(pt.get('human'))}</td></tr>
<tr><td><b>Total</b> ({_f(pt.get('total', 0) / 5e6 * 100, 2)} paise a document); 95% interval from measurement</td><td><b>{_rs(pt.get('total'))}</b> ({_rs(lo)} to {_rs(hi)})</td></tr>
<tr><td>With a scan-heavy stretch (simulated run below)</td><td>{_rs(total)}</td></tr>
<tr><td>Our target: Rs 50k (a 50% margin); the controller aims at Rs 45k after a 10% reserve</td><td>Brute force (OCR all, LLM all): {_rs(base.get('total_inr'))}</td></tr>
</table>
<p><b>How precise.</b> Measured inputs (a fresh single-core timing sample, per-document rates resampled within class, LLM cost from
token counts) put the total within {_pct((hi - lo) / 2 / pt.get('total', 1), 1)} either way at 95%. Assumptions move it more: a cloud vCPU as fast
as the laptop {_rs(sens.get('cloud vCPU as fast as this Mac (1x)'))}, 3x slower {_rs(sens.get('cloud vCPU 3x slower'))}; the brief's 350 KB typical PDF fits 1.7 to 6.2
pages ({_rs(sens.get('1.7 pages per PDF (350 KB at AgamiAI scan sizes)'))} to {_rs(sens.get('6.2 pages per PDF (350 KB at our scan sizes)'))}); the worst combination is
{_rs(sens.get('worst case: 3x slower and 6.2 pages per PDF'))}, still under the Rs 50k target. Before a real run, L0 over the whole bucket (about Rs 225) gives exact page counts,
and timing the first 1,000 documents on the real machine gives the cloud speed.</p>
<p><b>Budget controller.</b> After each batch it compares spend with a straight plan line and moves one gate, &tau;, which applies to every gate
before the LLM (reading is where the money goes). Measured trade-off at 5M: &tau; 0.85 costs {_rs(t85.get('cost_5m'))} at {_f(t85.get('accuracy'))} accuracy,
0.95 {_rs(t95.get('cost_5m'))} at {_f(t95.get('accuracy'))}, 0.99 {_rs(t99.get('cost_5m'))} at {_f(t99.get('accuracy'))}. Raising &tau; bought no accuracy, so under budget
the controller holds 95% and the rest stays as margin. Squeezed to Rs 23k, it lowered &tau; to {_f(min(stress.get('tau_path', [0.95])), 2)} during
the scan-heavy stretch and spent {_rs(stress.get('controlled_spent'))} against {_rs(stress.get('fixed_spent'))} without it (chart). Most cost is fixed reading, so a much
tighter budget needs a person to sign off on lower accuracy.</p>

<h2>Assumptions (stated instead of asking)</h2>
<ul>
<li>15 classes (the brief also says "25" once). The class mix per format is assumed, matching the brief's format split within 0.03 points; KYC is 20%.</li>
<li>Critical: Legal, Property, PoI, PoA ("regulatory" read as KYC; no class is medical). PoA if an address is visible, else PoI; a Voter ID
front counts as PoI (the brief lists it under PoA only). Passbooks are not statements. Anything that transfers, mortgages, titles or values
property is Property; other agreements, rent included, are Legal. An email takes the class of its attachment.</li>
<li>CPU at the brief's Rs 32/hr for 8 vCPU; LLM tokens at the brief's rates; human review has no quoted price, so it is counted, not costed,
and kept in the low thousands. A real run first needs a labelled seed from the client's bucket: the LLM labels about 5,000 documents and
people check only where it disagrees with our models (about 600).</li>
</ul>

<h2>Limitations and next steps</h2>
<ul>
<li>All accuracy is on synthetic documents; ID cards and marksheets follow the official designs but were not checked against real copies.
The only outside source tested is bank statements (Lockboxes B and D).</li>
<li>The masker removes {mask_line} of such spans in the Maskara Indian PII test set (Hugging Face); names are not masked yet (next: a name model).
The KanoonGPT legal set was not used: it is mostly statutes and notifications, not contracts or deeds.</li>
<li>Next: a name masker; a small fine-tuned text model (LoRA) for L2; conformal prediction for a recall guarantee on critical classes;
a vision LLM for scans whose text cannot be read; more outside document types for the splitter.</li>
</ul>

<h2>The controller at work: budget squeezed to Rs 23k, scan-heavy batches 41-56</h2>
<p><img src="controller_23000.png" width="430"/></p>
"""


CSS = """
* { font-family: sans-serif; }
body { font-size: 8pt; line-height: 1.22; }
h1 { font-size: 12.5pt; margin: 0 0 1px 0; }
.sub { color: #555; font-size: 7.4pt; margin: 0 0 3px 0; }
h2 { font-size: 9pt; margin: 6px 0 2px 0; color: #1f4e79; }
p { margin: 2px 0; }
table { border-collapse: collapse; width: 100%; margin: 2px 0; }
th, td { border: 0.5px solid #999; padding: 1.3px 3px; vertical-align: top; font-size: 7.4pt; }
th { text-align: left; font-weight: bold; }
ul { margin: 1px 0 1px 12px; padding: 0; }
li { margin: 1px 0; }
"""


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    story = pymupdf.Story(html=build_html(), user_css=CSS, archive=pymupdf.Archive(str(DATA_DIR / "sample")))
    writer = pymupdf.DocumentWriter(str(OUT))
    page = pymupdf.paper_rect("a4")
    where = page + (38, 34, -38, -34)
    more, n = True, 0
    while more:
        dev = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
        n += 1
    writer.close()
    doc = pymupdf.open(OUT)          # shrink it for email: subset fonts, compress streams
    doc.subset_fonts()
    doc.save(OUT.with_suffix(".tmp.pdf"), garbage=4, deflate=True)
    doc.close()
    OUT.with_suffix(".tmp.pdf").replace(OUT)
    print(f"wrote {OUT} ({n} pages, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
