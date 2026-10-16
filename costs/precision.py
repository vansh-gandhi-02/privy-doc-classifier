"""How precise is the 5M cost estimate?

The estimate is counts times unit costs:

  total = (L0 x files + L1 x all pages + selective read x scanned pages
           + page-number read x scanned pages of multi-page files
           + full read x files x E[full reads per document]) x cloud slowdown x Rs per core-second
          + files x P(LLM) x Rs per LLM call + files x P(human) x Rs per human review

Two kinds of uncertainty, reported separately:
1. Measurement: the unit times (costs/timing.py, one read per core), the
   per-document rates (resampled within class over the calib and dev-test
   documents, weighted by the assumed class mix, from scripts/run_controller_demo.py)
   and the LLM's rupees per call (its token counts). These give a 95% interval.
2. Assumptions nothing here can measure: how much slower a cloud vCPU is than
   this laptop, and pages per PDF. Shown one at a time as a sensitivity table.

Human review: the brief quotes no price, so it is costed at budget.yaml's
human_review_inr_per_doc (0); the count is reported (D30).

Run: python -m costs.precision   (after costs.timing and scripts.run_controller_demo)
"""
from __future__ import annotations

import json
import statistics

import numpy as np

from common.config import DATA_DIR, load
from costs.timing import INR_PER_CORE_S, PAGES_PER_PDF, pages

N_BOOT = 2000
CLOUD = 2.0
HUMAN_INR = load("budget")["human_review_inr_per_doc"]


def ci(xs) -> tuple[float, float]:
    xs = list(xs)
    return statistics.mean(xs), 1.96 * statistics.stdev(xs) / len(xs) ** 0.5


def total(t: dict, rates: dict, inr_call: float, slow=CLOUD, per_pdf=PAGES_PER_PDF, n=5e6) -> dict:
    all_p, scanned, multi = pages(n, per_pdf)
    cpu = {"L0": n * t["l0"], "L1": all_p * t["l1"], "selective": scanned * t["sel"], "page numbers": multi * t["cue"],
           "full reads": n * rates["reads"] * t["full"]}
    parts = {k: v * slow * INR_PER_CORE_S for k, v in cpu.items()}
    parts["LLM"] = n * rates["llm"] * inr_call
    parts["human"] = n * rates["human"] * HUMAN_INR
    parts["total"] = sum(parts.values())
    return parts


def main() -> None:
    root = DATA_DIR / "sample"
    samples = json.load(open(root / "timing_samples.json"))
    bench = json.load(open(DATA_DIR / "bench.json"))
    pool = json.load(open(root / "cost_pool.json"))
    l3m = json.load(open(root / "l3_metrics.json"))
    calls = [json.loads(line) for line in open(root / "l3_calls.jsonl")]
    calls = [c["inr"] for c in calls if c["mode"] == l3m["pick"]]

    sel, full, cue = ci(samples["selective"]), ci(samples["full"]), ci(samples["page_cue"])
    rs, dit = ci(samples["l1_render_signals"]), ci(samples["dit"])
    llm = (l3m["modes"][l3m["pick"]]["inr_per_call"], ci(calls)[1])   # the same point as the controller; spread from all calls
    t = {"l0": bench["l0_s_per_file"], "l1": rs[0] + dit[0], "sel": sel[0], "full": full[0], "cue": cue[0]}

    mix = load("class_mix")["classes"]
    by_cls = {}
    for d in pool:
        by_cls.setdefault(d["cls"], []).append(d)
    share = {c: mix[c]["share"] / sum(mix[k]["share"] for k in by_cls) for c in by_cls}

    def rates_of(groups):
        return {k: sum(share[c] * np.mean([d[f] for d in g]) for c, g in groups.items())
                for k, f in (("reads", "full_reads"), ("llm", "llm"), ("human", "human"))}

    rates = rates_of(by_cls)
    point = total(t, rates, llm[0])

    rng = np.random.default_rng(7)
    sims = []
    for _ in range(N_BOOT):
        groups = {c: [g[i] for i in rng.integers(0, len(g), len(g))] for c, g in by_cls.items()}
        tt = {"l0": t["l0"], "l1": rng.normal(rs[0], rs[1] / 1.96) + rng.normal(dit[0], dit[1] / 1.96),
              "sel": rng.normal(sel[0], sel[1] / 1.96), "full": rng.normal(full[0], full[1] / 1.96), "cue": rng.normal(cue[0], cue[1] / 1.96)}
        sims.append(total(tt, rates_of(groups), rng.normal(llm[0], llm[1] / 1.96))["total"])
    lo, hi = np.percentile(sims, [2.5, 97.5])

    print("Unit costs (CPU seconds on one core of this Mac; 95% interval of the mean):")
    for name, (m, h), n in (("selective read", sel, len(samples["selective"])), ("full read", full, len(samples["full"])),
                            ("page-number read", cue, len(samples["page_cue"])),
                            ("L1 render + signals", rs, len(samples["l1_render_signals"])), ("L1 DiT on CPU", dit, len(samples["dit"]))):
        print(f"  {name:22} {m:.3f} s +/- {h / m:.1%}  (n={n})")
    print(f"  LLM call ({l3m['pick']})       Rs {llm[0]:.4f} +/- {llm[1] / llm[0]:.1%}  (n={len(calls)}, from token counts)")
    print(f"\nPer-document rates (class-mix weighted, {len(pool)} documents): full reads {rates['reads']:.3f}, "
          f"LLM {rates['llm']:.4f}, human {rates['human']:.4f}")
    print(f"\n5M estimate at the default gate (cloud vCPU {CLOUD:g}x, {PAGES_PER_PDF:g} pages per PDF, human review at Rs {HUMAN_INR:g}):")
    for k, v in point.items():
        print(f"  {k:12} Rs {v:>9,.0f}")
    print(f"  95% interval from measurement: Rs {lo:,.0f} to Rs {hi:,.0f} "
          f"(-{(point['total'] - lo) / point['total']:.1%} / +{(hi - point['total']) / point['total']:.1%})")

    sens = []
    for label, kw in (("cloud vCPU as fast as this Mac (1x)", dict(slow=1.0)), ("cloud vCPU 1.5x slower", dict(slow=1.5)),
                      ("cloud vCPU 3x slower", dict(slow=3.0)),
                      ("1.7 pages per PDF (350 KB at AgamiAI scan sizes)", dict(per_pdf=1.7)), ("2 pages per PDF", dict(per_pdf=2.0)),
                      ("4 pages per PDF", dict(per_pdf=4.0)), ("6.2 pages per PDF (350 KB at our scan sizes)", dict(per_pdf=6.2)),
                      ("worst case: 3x slower and 6.2 pages per PDF", dict(slow=3.0, per_pdf=6.2))):
        sens.append((label, total(t, rates, llm[0], **kw)["total"]))
    print("\nAssumptions (one at a time, everything else as above):")
    for label, v in sens:
        print(f"  {label:48} Rs {v:>9,.0f}  ({(v - point['total']) / point['total']:+.0%})")
    n_human = 5e6 * rates["human"]
    print(f"\nHuman review: about {n_human:,.0f} documents at 5M (plus ~600 to check the labelled seed): low thousands.")
    print("Before committing to 5M: run L0 over the whole bucket (about Rs 60 of CPU plus Rs 165 of storage reads) for exact"
          " page counts, and time the first ~1,000 documents on the real cloud machine.")
    json.dump({"unit": {"selective": sel, "full": full, "page_cue": cue, "l1_render_signals": rs, "dit": dit, "llm_call": llm},
               "rates": rates, "point": point, "ci95": [lo, hi], "sensitivity": sens, "human_docs_5m": n_human},
              open(root / "cost_precision.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
