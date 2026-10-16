"""How one document moves through the pipeline: its class probabilities after every step.

Picks five dev-test documents that show the main paths, runs each through the
same code the pipeline uses (pipeline/run.py with trace=True), and draws one row
per document, one panel per step, with the 95% gate marked:

1. a scanned passbook: the interviewer's example. It shares its words with a bank
   statement, but the layout model (L1) tells them apart without reading.
2. a scanned Class 12 marksheet: layout narrows it to "a marksheet"; a selective
   read of a few lines ("Senior School") decides Class 10 vs 12.
3. an Aadhaar card with an address: the models decide "KYC ID document"; the
   address question splits it into Proof of Address.
4. a scanned Class 10 marksheet the reading steps leave unsure: the LLM quotes
   "SECONDARY EXAMINATION", and its answer (replayed from the cache) is weighed by
   its measured accuracy.
5. a scanned card application whose first page shows neither a card type nor a
   loan amount: the LLM says "none of these", so it goes to a person (L4).

Writes data/sample/how_a_document_moves.png and prints the numbers.
Run: python -m scripts.trace_document
"""
from __future__ import annotations

import csv
import json

import joblib
import numpy as np

from common.config import DATA_DIR, bucket_of, model_merge
from evaluation.metrics import ABSTAIN
from pipeline.l3_llm.llm import LLMSensor
from pipeline.run import run_to_l2
from scripts.run_l3_compare import update

SHORT = {"bank_statement": "Bank statement", "cc_statement": "Card statement", "kyc_id": "KYC ID document",
         "proof_of_identity": "Proof of Identity", "proof_of_address": "Proof of Address", "loan_application": "Loan application",
         "cc_application": "Card application", "salary_slip": "Salary slip", "itr": "ITR", "gst": "GST",
         "audited_financials": "Audited financials", "company_constitution": "Company constitution", "legal_contract": "Legal contract",
         "property_collateral": "Property", "class10_marksheet": "Class 10 marksheet", "class12_marksheet": "Class 12 marksheet",
         "other": "Other (passbook etc.)", "none_of_these": "none of these"}


def _pick(units, recs, calls):
    """The four example documents, chosen by what happened to them on dev-test."""
    by = {r["unit"]: r for r in recs}

    def first(cond):
        return next((u for u in units if u["split"] == "dev_test" and cond(u, by.get(u["unit"]))), None)

    image = lambda u: not u["native"].strip()
    return [
        ("A scanned passbook (true class: Other)", first(lambda u, r: u["subtype"] == "passbook_page" and image(u) and r and r["stop"] == "L1")),
        ("A scanned Class 12 marksheet", first(lambda u, r: u["cls"] == "class12_marksheet" and image(u) and r and r["stop"] == "selective read"
                                               and r["pred"] == u["cls"])),
        ("An Aadhaar card with an address (true class: Proof of Address)",
         first(lambda u, r: u["subtype"] == "aadhaar_back" and image(u) and r and r["stop"] == "address question")),
        ("A scanned Class 10 marksheet the reading steps could not settle: the LLM decides",
         first(lambda u, r: u["cls"] == "class10_marksheet" and r and r["pred"] == ABSTAIN and image(u) and u["unit"] in calls
               and calls[u["unit"]]["answer"] == u["cls"])),
        ("A scanned card application nothing could settle",
         first(lambda u, r: u["cls"] == "cc_application" and r and r["pred"] == ABSTAIN and image(u) and u["unit"] in calls)),
    ]


def main() -> None:
    root = DATA_DIR / "sample"
    units = [json.loads(line) for line in open(root / "text.jsonl")]
    recs = list(csv.DictReader(open(root / "l2_predictions.csv")))
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    pages = np.load(root / "pages.npz")
    row_of = {(k, int(p)): i for i, (k, p) in enumerate(zip(pages["key"], pages["page"]))}
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    model = joblib.load(DATA_DIR / "models" / "l2.joblib")
    check = joblib.load(DATA_DIR / "models" / "address.joblib")
    l3m = json.load(open(root / "l3_metrics.json"))
    s = l3m["modes"][l3m["pick"]]["sensor"]
    sensor = LLMSensor(s["acc"], s["none_in"], s["none_out"])
    calls = {}
    for line in open(root / "l3_calls.jsonl"):
        c = json.loads(line)
        if c["mode"] == l3m["pick"]:
            calls[c["unit"]] = c
    buckets, merged = bucket_of(), tuple(model_merge())

    rows = []
    for title, u in _pick(units, recs, calls):
        if u is None:
            continue
        start = 0
        if "#" in u["unit"]:
            key, j = u["unit"].split("#")
            start = json.loads(labels[key]["segments"])[int(j)]["start"] - 1
        r = row_of.get((u["key"], start))
        rec = run_to_l2(u, l1.likelihood(pages["feats"][[r]])[0] if r is not None else None, model, check, buckets, merged, trace=True)
        steps = list(rec["trace"])
        outcome = f"accepted: {SHORT.get(rec['pred'], rec['pred'])}" if rec["pred"] != ABSTAIN else "below 95%: on to the LLM"
        if rec["pred"] == ABSTAIN and u["unit"] in calls:
            c = calls[u["unit"]]
            probs = json.loads(rec["probs"])
            post = update(probs, sensor.likelihood(c["answer"], c["cands"], list(probs)))
            steps.append((f"L3: LLM answered\n{SHORT.get(c['answer'], c['answer'])}", post))
            top = max(post, key=post.get)
            outcome = f"accepted: {SHORT.get(top, top)}" if post[top] >= 0.95 else "below 95%: to a person"
        rows.append((title, u["cls"], steps, outcome))
        print(f"\n{title}  [{u['unit']}]  true class: {SHORT[u['cls']]}")
        for name, dist in steps:
            top3 = sorted(dist.items(), key=lambda kv: -kv[1])[:3]
            print(f"  {name.replace(chr(10), ' '):34} " + ", ".join(f"{SHORT.get(c, c)} {p:.1%}" for c, p in top3))
        print(f"  -> {outcome}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ncol = max(len(st) for _, _, st, _ in rows)
    fig, axes = plt.subplots(len(rows), ncol, figsize=(3.2 * ncol, 2.9 * len(rows)), squeeze=False)
    for i, (title, true, steps, outcome) in enumerate(rows):
        shown = []
        for _, dist in steps:  # the classes that matter at any step, in a fixed order for the row
            for c, _ in sorted(dist.items(), key=lambda kv: -kv[1])[:3]:
                if c not in shown:
                    shown.append(c)
        shown = shown[:6][::-1]
        for j in range(ncol):
            ax = axes[i][j]
            if j >= len(steps):
                ax.axis("off")
                continue
            name, dist = steps[j]
            vals = [dist.get(c, 0.0) for c in shown]
            colors = ["tab:green" if c == true or (c == "kyc_id" and true in ("proof_of_identity", "proof_of_address")) else "tab:gray" for c in shown]
            ax.barh(range(len(shown)), vals, color=colors)
            ax.axvline(0.95, color="tab:red", ls="--", lw=0.8)
            ax.set_xlim(0, 1)
            ax.set_yticks(range(len(shown)))
            ax.set_yticklabels([SHORT.get(c, c) for c in shown] if j == 0 else [], fontsize=7)
            ax.tick_params(axis="x", labelsize=6)
            ax.set_title(name, fontsize=8)
            for k, v in enumerate(vals):
                if v >= 0.05:
                    ax.text(min(v, 0.80) + 0.02, k, f"{v:.0%}", va="center", fontsize=6)
        axes[i][0].annotate(f"{i + 1}. {title}   \u2192   {outcome}", xy=(0, 1.30), xycoords="axes fraction", fontsize=9, fontweight="bold")
    fig.suptitle("How one document moves through the pipeline: class probabilities after each step "
                 "(green = true class; red line = the 95% gate)", fontsize=10)
    fig.subplots_adjust(left=0.09, right=0.99, top=0.93, bottom=0.03, hspace=0.95, wspace=0.22)
    out = root / "how_a_document_moves.png"
    fig.savefig(out, dpi=130)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
