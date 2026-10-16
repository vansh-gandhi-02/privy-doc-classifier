"""Write the two-page approach doc (deliverables/approach.pdf) from the measured results.

The prose lives in deliverables/approach.tex; every number in it is a \\N{key} that
this script fills from the metrics files the scripts write (deliverables/numbers.tex),
so the doc and the repo never disagree. It then compiles the PDF with tectonic
(a one-file LaTeX engine, https://tectonic-typesetting.github.io) if it is installed;
otherwise it stops after writing numbers.tex, and approach.tex compiles anywhere
XeLaTeX does (Overleaf included).

Run: python -m tools.make_doc
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path

from common.config import DATA_DIR, ROOT

DOCS = ROOT / "deliverables"
NAMES = {"proof_of_identity": "PoI", "proof_of_address": "PoA", "legal_contract": "Legal", "property_collateral": "Property"}


def _j(rel: str) -> dict:
    p = DATA_DIR / rel
    return json.load(open(p)) if p.exists() else {}


def _rows(rel: str) -> list[dict]:
    p = DATA_DIR / rel
    return list(csv.DictReader(open(p))) if p.exists() else []


def _inr(v: float) -> str:
    """Indian digit grouping: 130170 -> 1,30,170."""
    s = f"{round(v):d}"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head] + groups + [tail])


def _k(v: float) -> str:
    return f"{v / 1000:.1f}k"


def _pct(v: float, nd: int = 0) -> str:
    return f"{100 * v:.{nd}f}\\%"


def _crit(d: dict) -> str:
    if d and all(v == 1.0 for v in d.values()):
        return "1.00 on all four"
    return ", ".join(f"{NAMES.get(k, k)} {v:.2f}" for k, v in d.items())


def numbers() -> dict[str, str]:
    bench, l1, l2, l3 = _j("bench.json"), _j("sample/l1_metrics.json"), _j("sample/l2_metrics.json"), _j("sample/l3_metrics.json")
    ctl, stress, base, mask = _j("sample/controller.json"), _j("sample/controller_23000.json"), _j("sample/baseline.json"), _j("sample/masker_check.json")
    la, lb, lc, ld = (_j("lockbox_a/final_metrics.json"), _j("lockbox_b/diagnostics.json"), _j("lockbox_c/final_metrics.json"),
                      _j("lockbox_d/final_metrics.json"))
    spl = _j("sample/splitter_eval.json").get("agami_dev (80 fresh statements)", {})
    prec = _j("sample/cost_precision.json")
    pt, (lo, hi) = prec["point"], prec["ci95"]
    sens = dict(prec["sensitivity"])
    pick = l3["pick"]
    lab, chosen = l3["modes"]["label"], l3["modes"][pick]
    e2e = l3["end_to_end"][pick]
    trade = ctl["tradeoff"]
    mt = mask["real_world_eval"]
    llm_calls = prec["rates"]["llm"] * 5e6
    dev = sum(r["split"] == "dev_test" for r in _rows("sample/l2_predictions.csv"))
    return {
        # headline
        "total": _inr(pt["total"]), "total-round": _inr(round(pt["total"], -2)), "paise": f"{pt['total'] / 5e6 * 100:.2f}",
        "budget-share": _pct(pt["total"] / 1e5), "brute": _inr(base["total_inr"]),
        "worst": _inr(sens["worst case: 3x slower and 6.2 pages per PDF"]),
        "worst-round": _inr(round(sens["worst case: 3x slower and 6.2 pages per PDF"], -2)),
        "no-llm": _pct(l2["settled"], 1), "human-docs": _inr(round(prec["human_docs_5m"], -2)),
        "human-share": _pct(prec["human_docs_5m"] / 5e6, 2),
        # steps
        "l0-ms": f"{bench['l0_s_per_file'] * 1000:.0f}", "l1-s": f"{bench['l1_s_per_page']:.2f}",
        "sel-s": f"{bench['ocr_selective_s']:.2f}", "full-s": f"{bench['ocr_full_s']:.1f}",
        "l1-settles": _pct(l1["accept_rate"]), "l1-acc": _pct(l1["accepted_accuracy"], 1),
        "llm-call": f"{chosen['inr_per_call']:.3f}", "settled-acc": _pct(l2["settled_accuracy"], 1),
        # gates
        "t85-cost": _k(trade["0.85"]["cost_5m"]), "t85-acc": _pct(trade["0.85"]["accuracy"], 1),
        "t95-cost": _k(trade["0.95"]["cost_5m"]), "t95-acc": _pct(trade["0.95"]["accuracy"], 1),
        "t99-cost": _k(trade["0.99"]["cost_5m"]), "t99-acc": _pct(trade["0.99"]["accuracy"], 1),
        "stress-tau": f"{min(stress['tau_path']):.2f}", "stress-spent": _inr(stress["controlled_spent"]),
        "stress-fixed": _inr(stress["fixed_spent"]),
        "label-acc": _pct(lab["accuracy_hard"], 1), "label-call": f"{lab['inr_per_call']:.3f}",
        "quote-acc": _pct(chosen["accuracy_hard"], 1),
        "quote-extra": _inr(round((chosen["inr_per_call"] - lab["inr_per_call"]) * llm_calls, -2)),
        # results
        "dev-n": _inr(dev), "dev-f1": f"{e2e['macro_f1_l4_as_error']:.3f}", "dev-crit": _crit(e2e["critical_recall"]),
        "dev-llm": _pct(l2["l3_docs_5m"] / 5e6, 1), "dev-l4": _pct(e2e["l4_share_dev"], 1),
        "a-n": _inr(la["n_records"]), "a-files": _inr(len(_rows("lockbox_a/manifest.csv"))),
        "a-f1": f"{la['macro_f1_abstain_as_error']:.3f}", "a-crit": _crit(la["critical_recall"]),
        "a-llm": str(la["llm_calls"]), "a-l4": str(la["l4_docs"]),
        "c-n": _inr(lc["n_records"]), "c-f1": f"{lc['macro_f1_abstain_as_error']:.3f}", "c-crit": _crit(lc["critical_recall"]),
        "c-llm": str(lc["llm_calls"]), "c-l4": str(lc["l4_docs"]),
        "b-pieces": f"{lb['pieces_per_file']:.1f}",
        "d-whole": ld["singles_kept_whole"], "d-right": ld["first_document_right"], "d-llm": str(ld["llm_calls"]), "d-l4": str(ld["l4_docs"]),
        "spl-before": spl["layout only"]["kept_whole"], "spl-after": spl["with page numbers"]["kept_whole"],
        "f1-min": f"{min(e2e['macro_f1_l4_as_error'], la['macro_f1_abstain_as_error'], lc['macro_f1_abstain_as_error']):.3f}",
        "f1-max": f"{max(e2e['macro_f1_l4_as_error'], la['macro_f1_abstain_as_error'], lc['macro_f1_abstain_as_error']):.3f}",
        "crit-min": f"{min(list(la['critical_recall'].values()) + list(lc['critical_recall'].values())):.2f}",
        # cost
        "c-look": _inr(pt["L0"] + pt["L1"]), "c-sel": _inr(pt["selective"] + pt["page numbers"]), "c-full": _inr(pt["full reads"]),
        "c-llm-share": _pct(prec["rates"]["llm"], 1), "c-llmcost": _inr(pt["LLM"]), "c-human": _inr(pt["human"]),
        "ci-lo": _inr(lo), "ci-hi": _inr(hi), "ci-pm": _pct((hi - lo) / 2 / pt["total"], 1),
        "s-1x": _k(sens["cloud vCPU as fast as this Mac (1x)"]), "s-3x": _k(sens["cloud vCPU 3x slower"]),
        "s-p17": _k(sens["1.7 pages per PDF (350 KB at AgamiAI scan sizes)"]), "s-p62": _k(sens["6.2 pages per PDF (350 KB at our scan sizes)"]),
        # masker
        **{f"m-{lab_}": _pct(mt[key]["masked"]) for key, lab_ in (("PAN_CARD", "pan"), ("DRIVER_LICENSE", "dl"), ("EMAIL", "email"),
                                                                 ("UPI_ID", "upi"), ("AADHAAR", "aadhaar"), ("PHONE", "phone"),
                                                                 ("DATE_OF_BIRTH", "dob"), ("PERSON_NAME", "name"))},
    }


def main() -> None:
    nums = numbers()
    lines = ["% Written by tools/make_doc.py from the metrics files. Do not edit by hand."]
    lines += [f"\\expandafter\\def\\csname n:{k}\\endcsname{{{v}}}" for k, v in nums.items()]
    (DOCS / "numbers.tex").write_text("\n".join(lines) + "\n")
    print(f"wrote {DOCS / 'numbers.tex'} ({len(nums)} numbers)")
    tex = shutil.which("tectonic") or str(Path.home() / ".local" / "bin" / "tectonic")
    if not Path(tex).exists():
        print("tectonic not found: compile deliverables/approach.tex with XeLaTeX to get the PDF")
        return
    subprocess.run([tex, "-X", "compile", "approach.tex"], cwd=DOCS, check=True, capture_output=True)
    out = DOCS / "approach.pdf"
    import pymupdf
    pages = len(pymupdf.open(out))
    print(f"wrote {out} ({pages} pages, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
