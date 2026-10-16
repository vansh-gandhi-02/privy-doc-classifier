"""The budget controller on a simulated 5M-document run (walkthrough step 7, D28).

The controller's gate tau applies to every gate before the LLM (L1, each rung of
the reading ladder, the L2 -> LLM gate), because reading, not the LLM, is where
most of the money goes. Critical documents keep 95% whatever tau is.

For every calibration and dev-test document, the whole path (pipeline/run.py)
is re-run at each tau on a grid, so its reads, its cost and its label are known
at any setting. Documents that reach the LLM use their cached `claude -p`
answer when there is one (run_l3_compare.py); the few without one are counted
at the LLM's measured accuracy.

The run is 100 batches of 50,000 documents drawn from that pool by the assumed
class mix (class_mix.yaml); batches 40-55 are scan-heavy (images and scans
only). After each batch the controller compares spend with the plan line and
moves tau (pipeline/controller.py). It raises tau above 95% only if that is
measured to buy accuracy; otherwise unspent budget stays as margin.

Cost per document (cloud vCPU taken as 2x slower than this Mac): L0, L1 and the
selective read of every scanned page (fixed, from the bench); the full-page and
later-page reads this document needed at this tau; an LLM call; Rs 1 for a human.

Writes data/sample/controller[_<target>].png and .json.
Run: python -m scripts.run_controller_demo [target_inr]
"""
from __future__ import annotations

import csv
import json
import random
import sys

import joblib
import numpy as np

from common.config import DATA_DIR, bucket_of, load, model_merge
from evaluation.metrics import ABSTAIN
from pipeline.controller import BudgetController
from pipeline.run import run_to_l2
from pipeline.l3_llm.llm import LLMSensor
from scripts.run_l3_compare import update

CLOUD = 2.0
INR_PER_CORE_S = 32 / 8 / 3600
HUMAN_INR = load("budget")["human_review_inr_per_doc"]
BATCHES, BATCH_DOCS, DRAWS = 100, 50_000, 1500
SURPRISE = range(40, 56)
GRID = (0.85, 0.87, 0.89, 0.91, 0.93, 0.95, 0.97, 0.99)


def main(target: str | None = None) -> None:
    root = DATA_DIR / "sample"
    budget = load("budget")
    target_inr = float(target) if target else budget["target_compute_inr"] * (1 - budget["reserve_fraction"])
    bench = json.load(open(DATA_DIR / "bench.json"))
    l3m = json.load(open(root / "l3_metrics.json"))
    mode = l3m["pick"]
    s = l3m["modes"][mode]["sensor"]
    sensor = LLMSensor(s["acc"], s["none_in"], s["none_out"])
    inr_call = l3m["modes"][mode]["inr_per_call"]
    calls = {}
    for line in open(root / "l3_calls.jsonl"):
        c = json.loads(line)
        if c["mode"] == mode:
            calls[c["unit"]] = c

    units = [json.loads(line) for line in open(root / "text.jsonl")]
    units = [u for u in units if u["split"] in ("calib", "dev_test")]
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    pages = np.load(root / "pages.npz")
    row_of = {(k, int(p)): i for i, (k, p) in enumerate(zip(pages["key"], pages["page"]))}
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    model = joblib.load(DATA_DIR / "models" / "l2.joblib")
    check = joblib.load(DATA_DIR / "models" / "address.joblib")
    buckets, merged = bucket_of(), tuple(model_merge())
    fixed_5m = sum(v for k, v in bench["inr"].items() if not k.startswith("OCR full"))
    mix = load("class_mix")["classes"]
    n_cls = {}
    for u in units:
        n_cls[u["cls"]] = n_cls.get(u["cls"], 0) + 1
    w_unit = np.array([mix[u["cls"]]["share"] / n_cls[u["cls"]] for u in units])
    image_share = float(np.sum(w_unit * np.array([not u["native"].strip() for u in units])) / w_unit.sum())
    fixed_image = fixed_5m * CLOUD / 5e6 / image_share   # L0/L1/selective reads fall on scanned documents (class-mix weighted)
    rng = random.Random(11)

    def start(u):
        if "#" not in u["unit"]:
            return 0
        key, j = u["unit"].split("#")
        return json.loads(labels[key]["segments"])[int(j)]["start"] - 1

    print(f"re-running the path for {len(units)} documents at {len(GRID)} gate settings...", flush=True)
    pool = []
    for u in units:
        r = row_of.get((u["key"], start(u)))
        l1_lik = l1.likelihood(pages["feats"][[r]])[0] if r is not None else None
        image = not u["native"].strip()
        at = {}
        for tau in GRID:
            rec = run_to_l2(u, l1_lik, model, check, buckets, merged, tau=tau)
            comp = {"fixed": fixed_image if image else 0.0,
                    "reads": (rec["full1"] * bench["ocr_full_s"] + rec["more"] * max(rec["n_more"], 1) * bench["ocr_full_s"]) * INR_PER_CORE_S * CLOUD,
                    "llm": 0.0, "human": 0.0}
            label, step = rec["pred"], "L2"
            if label == ABSTAIN:
                comp["llm"] = inr_call
                step = "L3"
                c = calls.get(u["unit"])
                if c is not None:
                    probs = json.loads(rec["probs"])
                    post = update(probs, sensor.likelihood(c["answer"], c["cands"], list(probs)))
                    top = max(post, key=post.get)
                    label = top if post[top] >= 0.95 else ABSTAIN
                else:  # no cached answer: the LLM's measured accuracy
                    label = u["cls"] if rng.random() < sensor.acc else ABSTAIN
                if label == ABSTAIN:
                    comp["human"] = HUMAN_INR
                    step = "L4"
            at[tau] = (sum(comp.values()), label, step, comp)
            if tau == 0.95:
                n_reads = rec["full1"] + rec["more"] * max(rec["n_more"], 1)
        pool.append(dict(cls=u["cls"], split=u["split"], image=image, at=at, n_reads_95=n_reads))

    mix = load("class_mix")["classes"]
    counts = {}
    for d in pool:
        counts[d["cls"]] = counts.get(d["cls"], 0) + 1
    weights = np.array([mix[d["cls"]]["share"] / counts[d["cls"]] for d in pool])
    dev = [d for d in pool if d["split"] == "dev_test"]
    # Per-document counts at the default gate, for the cost-precision check (costs/precision.py).
    json.dump([dict(cls=d["cls"], image=d["image"], full_reads=d["n_reads_95"], llm=int(d["at"][0.95][2] != "L2"),
                    human=int(d["at"][0.95][2] == "L4")) for d in pool], open(root / "cost_pool.json", "w"))

    print(f"\nL3 mode {mode} (Rs {inr_call:.4f}/call); target Rs {target_inr:,.0f} (after the {budget['reserve_fraction']:.0%} reserve)")
    print(f"{'tau':>5} {'Rs at 5M':>10} {'to L3':>7} {'to L4':>7} {'accuracy (L4 as error)':>23}")
    trade = {}
    for tau in GRID:
        cost5m = float(np.sum(weights * np.array([d["at"][tau][0] for d in pool])) / weights.sum() * 5e6)
        acc = float(np.mean([d["at"][tau][1] == d["cls"] for d in dev]))
        l3 = float(np.mean([d["at"][tau][2] != "L2" for d in dev]))
        l4 = float(np.mean([d["at"][tau][2] == "L4" for d in dev]))
        trade[tau] = dict(cost_5m=cost5m, to_l3=l3, to_l4=l4, accuracy=acc)
        print(f"{tau:5.2f} {cost5m:10,.0f} {l3:7.1%} {l4:7.1%} {acc:23.3f}")
    allow_raise = trade[0.99]["accuracy"] > trade[0.95]["accuracy"]
    print(f"raising tau above 95% {'buys' if allow_raise else 'does not buy'} accuracy on dev-test, so the controller "
          f"{'may' if allow_raise else 'will not'} raise it")

    def nearest(tau):
        return min(GRID, key=lambda g: abs(g - tau))

    def run(controlled: bool):
        ctl = BudgetController(target_inr, BATCHES * BATCH_DOCS, allow_raise=allow_raise)
        spent, steps, rows = 0.0, {"L2": 0.0, "L3": 0.0, "L4": 0.0}, []
        parts = {"fixed": 0.0, "reads": 0.0, "llm": 0.0, "human": 0.0}
        draw_rng = random.Random(5)
        for b in range(BATCHES):
            cand = [i for i, d in enumerate(pool) if d["image"]] if b in SURPRISE else list(range(len(pool)))
            draw = draw_rng.choices(cand, weights=weights[cand], k=DRAWS)
            tau = nearest(ctl.threshold)
            outs = [pool[i]["at"][tau] for i in draw]
            spent += np.mean([o[0] for o in outs]) * BATCH_DOCS
            for o in outs:
                steps[o[2]] += BATCH_DOCS / DRAWS
                for k, v in o[3].items():
                    parts[k] += v * BATCH_DOCS / DRAWS
            rows.append((b, ctl.threshold, spent, ctl.planned_spend((b + 1) * BATCH_DOCS)))
            if controlled:
                ctl.adjust((b + 1) * BATCH_DOCS, spent)
        return rows, spent, steps, parts

    fixed_rows, fixed_spent, _, _ = run(False)
    ctl_rows, ctl_spent, ctl_steps, ctl_parts = run(True)
    print("spend by item (controlled run): " + ", ".join(f"{k} Rs {v:,.0f}" for k, v in ctl_parts.items()))
    print(f"\nwithout the controller (tau fixed at 0.95): spent Rs {fixed_spent:,.0f}")
    print(f"with the controller: spent Rs {ctl_spent:,.0f} against Rs {target_inr:,.0f}; tau ended at {ctl_rows[-1][1]:.3f} "
          f"(lowest {min(r[1] for r in ctl_rows):.3f}, highest {max(r[1] for r in ctl_rows):.3f})")
    print("documents by final step (controlled run): " + ", ".join(f"{k} {v:,.0f}" for k, v in ctl_steps.items()))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
    x = [r[0] + 1 for r in ctl_rows]
    ax[0].plot(x, [r[3] / 1000 for r in ctl_rows], "k--", label=f"plan (target Rs {target_inr / 1000:.0f}k)")
    ax[0].plot(x, [r[2] / 1000 for r in fixed_rows], color="grey", label="no controller (tau 0.95)")
    ax[0].plot(x, [r[2] / 1000 for r in ctl_rows], color="tab:blue", label="with controller")
    ax[0].axvspan(SURPRISE.start + 1, SURPRISE.stop, color="tab:orange", alpha=0.15, label="scan-heavy batches")
    ax[0].set_ylabel("spent (Rs thousand)")
    ax[0].legend(fontsize=8)
    ax[1].plot(x, [r[1] for r in ctl_rows], color="tab:blue")
    ax[1].axvspan(SURPRISE.start + 1, SURPRISE.stop, color="tab:orange", alpha=0.15)
    ax[1].set_ylabel("gate tau")
    ax[1].set_xlabel("batch (50,000 documents each)")
    fig.suptitle("Budget controller on a simulated 5M-document run")
    fig.tight_layout()
    tag = "" if target is None else f"_{int(target_inr)}"
    fig.savefig(root / f"controller{tag}.png", dpi=130)
    json.dump({"mode": mode, "target_inr": target_inr, "fixed_spent": fixed_spent, "controlled_spent": ctl_spent,
               "tau_path": [r[1] for r in ctl_rows], "tradeoff": trade, "steps": ctl_steps, "parts": ctl_parts, "allow_raise": allow_raise},
              open(root / f"controller{tag}.json", "w"), indent=1, default=float)
    print(f"wrote {root / f'controller{tag}.png'}")


if __name__ == "__main__":
    main(*sys.argv[1:])
