"""Compare three ways of asking the LLM (DECISIONS D25, 4d) and pick one by a rule set in advance.

Hard set: calibration and dev-test documents that L2 sent on to L3, plus those
it settled below 99% (so there are enough to measure), up to 150.
Modes: label only, quote-then-label, and thinking at maximum effort.

Per mode: accuracy on the hard set, tokens (thinking separately), rupees per
call at the brief's rates, and seconds. The sensor (4c) is counted on the
calibration half and applied to the dev-test half: how many L3 documents then
cross 95%, how accurate they are, and what is left for L4. A two-tier option
(no thinking first, thinking only for what is still unsettled) is simulated
from the same calls.

Rule (agreed 16 Oct): use the cheapest mode whose accuracy on the calibration
hard set is at least 95%; if none reaches it, use thinking and send the rest to L4.

Calls run on the Claude Code subscription (`claude -p`), four at a time, and
are cached in data/sample/l3_calls.jsonl, so a stopped run resumes.

Run: python -m scripts.run_l3_compare
"""
from __future__ import annotations

import csv
import json
import random
import shutil
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from common.config import DATA_DIR, class_ids, critical_classes, load
from evaluation.metrics import ABSTAIN, meets_bar
from pipeline.l3_llm.llm import NONE, LLMSensor, call, candidates

MODES = ("label", "quote", "think")
HARD_MAX = 150
THRESHOLD = 0.95
HUMAN_INR = load("budget")["human_review_inr_per_doc"]


def text_of(u: dict) -> str:
    if len(u["native"].strip()) >= 20:
        return u["native"]
    return (u["full1"] + "\n" + u["more"]).strip() or u["sel"]


def correct(answer, truth, cands) -> bool:
    return answer == (truth if truth in cands else NONE)


def _wilson_lower(k: int, n: int, z: float = 1.645) -> float:
    if n == 0:
        return 0.0
    p = k / n
    centre = p + z * z / (2 * n)
    spread = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (centre - spread) / (1 + z * z / n)


def fit_sensor(rows: list[dict]) -> LLMSensor:
    offered = [r for r in rows if r["cls"] in r["cands"]]
    not_offered = [r for r in rows if r["cls"] not in r["cands"]]
    acc = (sum(r["answer"] == r["cls"] for r in offered) + 1) / (len(offered) + 2)
    none_in = (sum(r["answer"] == NONE for r in offered) + 0.5) / (len(offered) + 2)
    none_out = (sum(r["answer"] == NONE for r in not_offered) + 1) / (len(not_offered) + 2)
    return LLMSensor(acc, none_in, none_out)


def update(probs: dict[str, float], lik: dict[str, float]) -> dict[str, float]:
    out = {c: p * lik.get(c, 1.0) for c, p in probs.items()}
    z = sum(out.values())
    return {c: p / z for c, p in out.items()}


def main() -> None:
    root = DATA_DIR / "sample"
    preds = list(csv.DictReader(open(root / "l2_predictions.csv")))
    units = {json.loads(line)["unit"]: json.loads(line) for line in open(root / "text.jsonl")}
    for r in preds:
        r["probs"] = json.loads(r["probs"])
        r["conf"] = float(r["conf"])
    to_l3 = [r for r in preds if r["pred"] == ABSTAIN]
    unsure = [r for r in preds if r["pred"] != ABSTAIN and r["conf"] < 0.99]
    random.Random(7).shuffle(unsure)
    crit_set = set(critical_classes())
    unsure.sort(key=lambda r: r["pred"] not in crit_set)  # critical ones first, for the 99% gate test
    hard = (to_l3 + unsure)[:HARD_MAX]
    print(f"documents settled below 99%: {len(unsure)} ({sum(r['pred'] in crit_set for r in unsure)} as a critical class)")
    print(f"hard set: {len(hard)} ({len(to_l3)} sent to L3 by L2, the rest settled below 99%); "
          f"calib {sum(r['split'] == 'calib' for r in hard)}, dev-test {sum(r['split'] == 'dev_test' for r in hard)}")

    cache_path = root / "l3_calls.jsonl"
    done = {}
    if cache_path.exists():
        for line in open(cache_path):
            c = json.loads(line)
            done[(c["unit"], c["mode"])] = c
    jobs = [(r, m) for r in hard for m in MODES if (r["unit"], m) not in done]
    print(f"{len(done)} calls cached, {len(jobs)} to make")
    if jobs and shutil.which("claude") is None:  # e.g. on Colab: replay the cache only
        print("no `claude` CLI here: using cached answers only")
        hard = [r for r in hard if all((r["unit"], m) in done for m in MODES)]
        jobs = []

    def run(job):
        r, m = job
        cands = candidates(r["probs"])
        res = call(text_of(units[r["unit"]]), cands, m)
        return dict(unit=r["unit"], mode=m, cands=cands, answer=res.answer, raw=res.raw[-300:], in_tokens=res.in_tokens,
                    out_tokens=res.out_tokens, thinking_tokens=res.thinking_tokens, seconds=res.seconds, inr=res.inr)

    with ThreadPoolExecutor(4) as pool, open(cache_path, "a") as f:
        for i, c in enumerate(pool.map(run, jobs), 1):
            f.write(json.dumps(c) + "\n")
            f.flush()
            done[(c["unit"], c["mode"])] = c
            if i % 50 == 0:
                print(f"  {i}/{len(jobs)} calls", flush=True)

    labels_all = list(preds[0]["probs"])
    results = {}
    for m in MODES:
        rows = []
        for r in hard:
            c = done[(r["unit"], m)]
            rows.append({**r, **{k: c[k] for k in ("cands", "answer", "in_tokens", "out_tokens", "thinking_tokens", "seconds", "inr")}})
        cal = [x for x in rows if x["split"] == "calib"]
        dev = [x for x in rows if x["split"] == "dev_test"]
        sensor = fit_sensor(cal)
        acc_all = np.mean([correct(x["answer"], x["cls"], x["cands"]) for x in rows])
        acc_cal = np.mean([correct(x["answer"], x["cls"], x["cands"]) for x in cal])
        settled = []
        for x in dev:
            post = update(x["probs"], sensor.likelihood(x["answer"], x["cands"], labels_all))
            top = max(post, key=post.get)
            x["l3_pred"] = top if post[top] >= THRESHOLD else ABSTAIN
            settled.append(x)
        l3_dev = [x for x in settled if x["pred"] == ABSTAIN]
        results[m] = dict(
            accuracy_hard=float(acc_all), accuracy_calib=float(acc_cal), n_calib=len(cal), parse_failures=sum(x["answer"] is None for x in rows),
            truth_offered=float(np.mean([x["cls"] in x["cands"] for x in rows])),
            sensor=dict(acc=sensor.acc, none_in=sensor.none_in, none_out=sensor.none_out),
            in_tokens=float(np.mean([x["in_tokens"] for x in rows])), out_tokens=float(np.mean([x["out_tokens"] for x in rows])),
            thinking_tokens=float(np.mean([x["thinking_tokens"] for x in rows])), inr_per_call=float(np.mean([x["inr"] for x in rows])),
            seconds=float(np.mean([x["seconds"] for x in rows])),
            l3_dev_n=len(l3_dev), l3_dev_settled=sum(x["l3_pred"] != ABSTAIN for x in l3_dev),
            l3_dev_settled_right=sum(x["l3_pred"] == x["cls"] for x in l3_dev),
            preds={x["unit"]: x["l3_pred"] for x in l3_dev},
            preds_all={x["unit"]: x["l3_pred"] for x in dev})

    print(f"\n{'mode':7} {'acc hard':>9} {'acc calib':>10} {'offered':>8} {'in tok':>7} {'out tok':>8} {'think':>6} {'Rs/call':>8} {'sec':>5}  L3 docs on dev-test settled (right)")
    for m, r in results.items():
        print(f"{m:7} {r['accuracy_hard']:9.3f} {r['accuracy_calib']:10.3f} {r['truth_offered']:8.1%} {r['in_tokens']:7.0f} "
              f"{r['out_tokens']:8.0f} {r['thinking_tokens']:6.0f} {r['inr_per_call']:8.4f} {r['seconds']:5.1f}  "
              f"{r['l3_dev_settled']}/{r['l3_dev_n']} ({r['l3_dev_settled_right']})")

    # Two tiers: a no-thinking mode first, thinking only where still unsettled (its answer replaces the first).
    for first in ("label", "quote"):
        a, t = results[first]["preds"], results["think"]["preds"]
        final = {u: (a[u] if a[u] != ABSTAIN else t[u]) for u in a}
        share_think = np.mean([a[u] == ABSTAIN for u in a]) if a else 0
        cost = results[first]["inr_per_call"] + share_think * results["think"]["inr_per_call"]
        results[f"{first}+think"] = dict(preds=final, inr_per_call=float(cost), share_second_call=float(share_think),
                                         l3_dev_n=len(final), l3_dev_settled=sum(v != ABSTAIN for v in final.values()))
        print(f"{first}+think: thinking needed on {share_think:.0%} of L3 documents; Rs {cost:.4f} per L3 document; "
              f"settles {results[f'{first}+think']['l3_dev_settled']}/{len(final)}")

    for m in MODES:
        k, n = round(results[m]["accuracy_calib"] * results[m]["n_calib"]), results[m]["n_calib"]
        results[m]["calib_lower_bound"] = _wilson_lower(k, n)
    eligible_now = [m for m in MODES if results[m]["calib_lower_bound"] >= 0.95]
    pick_now = min(eligible_now, key=lambda m: results[m]["inr_per_call"]) if eligible_now else "think"

    # End to end on dev-test, per option, and cost at 5M.
    l2m = json.load(open(root / "l2_metrics.json"))
    n_l3 = l2m["l3_docs_5m"]
    dev_all = [r for r in preds if r["split"] == "dev_test"]
    scored, crit = class_ids(scored_only=True), critical_classes()
    print(f"\nend to end on dev-test (n={len(dev_all)}); at 5M about {n_l3:,.0f} documents reach L3:")
    summary = {}
    for name, r in results.items():
        y_pred = [r["preds"].get(x["unit"], x["pred"]) if x["pred"] == ABSTAIN else x["pred"] for x in dev_all]
        y_true = [x["cls"] for x in dev_all]
        bar = meets_bar(y_true, y_pred, scored, crit)
        l4_share = np.mean([p == ABSTAIN for p in y_pred])
        l4_of_l3 = (r["l3_dev_n"] - r["l3_dev_settled"]) / max(r["l3_dev_n"], 1)
        llm_inr = n_l3 * r["inr_per_call"]
        human_inr = n_l3 * l4_of_l3 * HUMAN_INR
        if name == pick_now:  # the dev-test predictions after L3, for scripts/report_bar.py
            with open(root / "final_dev_predictions.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["unit", "true", "pred"])
                w.writerows([(x["unit"], t, p) for x, t, p in zip(dev_all, y_true, y_pred)])
        summary[name] = dict(macro_f1_l4_as_error=bar["macro_f1_abstain_as_error"], macro_f1_l4_excluded=bar["macro_f1_abstain_excluded"],
                             critical_recall=bar["critical_recall"], l4_share_dev=float(l4_share), llm_inr_5m=llm_inr, human_inr_5m=human_inr)
        print(f"  {name:12} macro-F1 {bar['macro_f1_abstain_as_error']:.3f} (L4 as error) / {bar['macro_f1_abstain_excluded']:.3f} (L4 left out); "
              f"to L4 {l4_share:.1%}; at 5M: LLM Rs {llm_inr:,.0f} + humans Rs {human_inr:,.0f} = Rs {llm_inr + human_inr:,.0f}")
        print("               critical recall (L4 as miss): " + ", ".join(f"{c.split('_')[0]} {v:.3f}" for c, v in bar["critical_recall"].items()))

    # Option: a stricter gate for critical classes. A document settled by L2 as Legal, Property,
    # PoI or PoA below 99% goes to the LLM too (it may be a confident mistake between two critical classes).
    for m in MODES:
        pa = results[m]["preds_all"]
        moved = [x for x in dev_all if x["pred"] != ABSTAIN and x["pred"] in crit and x["conf"] < 0.99 and x["unit"] in pa]
        fixed = sum(x["pred"] != x["cls"] and pa[x["unit"]] == x["cls"] for x in moved)
        broke = sum(x["pred"] == x["cls"] and pa[x["unit"]] not in (x["cls"], ABSTAIN) for x in moved)
        to_l4 = sum(pa[x["unit"]] == ABSTAIN for x in moved)
        results[m]["critical_99"] = dict(extra_llm_share=len(moved) / len(dev_all), fixed=fixed, broke=broke, extra_l4=to_l4,
                                         errors_before=sum(x["pred"] != x["cls"] for x in moved))
        print(f"  critical gate 99% ({m}): {len(moved)} more dev-test documents to the LLM ({len(moved) / len(dev_all):.1%}); "
              f"errors among them {results[m]['critical_99']['errors_before']}, fixed {fixed}, newly wrong {broke}, to L4 {to_l4}")

    # The rule (D25, refined in D28): the cheapest mode whose calibration accuracy is at least 95% with
    # confidence, i.e. the lower 90% Wilson bound clears 95%. On ~66 documents a point estimate is noisy.
    for m in MODES:
        k, n = round(results[m]["accuracy_calib"] * results[m]["n_calib"]), results[m]["n_calib"]
        results[m]["calib_lower_bound"] = _wilson_lower(k, n)
    eligible = [m for m in MODES if results[m]["calib_lower_bound"] >= 0.95]
    pick = min(eligible, key=lambda m: results[m]["inr_per_call"]) if eligible else "think"
    print("\ncalibration accuracy, lower 90% bound: " + ", ".join(f"{m} {results[m]['calib_lower_bound']:.3f}" for m in MODES))
    print(f"rule: cheapest mode whose lower bound clears 95% -> {pick}"
          + ("" if eligible else " (none did, so thinking, with the rest to L4)"))
    json.dump({"pick": pick, "modes": {m: {k: v for k, v in r.items() if k not in ("preds", "preds_all")} for m, r in results.items()},
               "end_to_end": summary},
              open(root / "l3_metrics.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
