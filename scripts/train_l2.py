"""Train, calibrate and check L2 (text) and the address question, then run
L0 -> L1 -> L2 -> address question on dev-test the way the pipeline will
(walkthrough step 3, DECISIONS D23 and D24).

Needs data/sample/text.jsonl (python -m scripts.extract_text) and the L1 model.

Reports:
- text alone, per reading depth: what each rung's text is worth
- the discriminator table for the pairs L1 leaves
- the address question on KYC documents: PoI and PoA recall
- the combined path: how many documents each step settles, how accurate they
  are, how many go on to the LLM, macro-F1 both ways (D8), critical recall
- where documents stop, by bucket, and what L2's reading costs at 5M

Run: python -m scripts.train_l2
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict

import joblib
import numpy as np
from scipy import sparse
from scipy.optimize import minimize_scalar
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from common.config import DATA_DIR, bucket_of, class_ids, critical_classes, load, model_class_ids, model_merge, to_model_class
from evaluation.metrics import ABSTAIN, meets_bar
from pipeline.l2_text.address import LEVELS, AddressCheck, level
from pipeline.run import address_text, run_to_l2, view_text, views_of
from pipeline.l0_open.metadata import poa_share
from pipeline.l2_text.text_model import VIEWS, TextModel
from pipeline.l2_text.features import id_features, normalise

THRESHOLD = 0.95
INR_PER_CORE_S = 32 / 8 / 3600   # the brief's CPU instance: Rs 32/hr for 8 vCPU
PAIRS = [("loan_application", "cc_application"), ("class10_marksheet", "class12_marksheet"),
         ("legal_contract", "property_collateral"), ("bank_statement", "cc_statement"), ("salary_slip", "itr")]


def _nll(p, y):
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1))))


def train(units: list[dict], classes: list[str]) -> TextModel:
    idx = {c: i for i, c in enumerate(classes)}

    def rows(split):
        r = [(view_text(u, v), idx[to_model_class(u["cls"])], v) for u in units if u["split"] == split for v in views_of(u)]
        return [t for t, _, _ in r], np.array([y for _, y, _ in r]), np.array([v for _, _, v in r])

    tx, ty, _ = rows("train")
    cx, cy, cv = rows("calib")
    vec = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, sublinear_tf=True, max_features=80000, dtype=np.float32)
    w_tr = vec.fit_transform([normalise(t) for t in tx])
    id_tr = np.stack([id_features(t) for t in tx])
    id_scaler = StandardScaler().fit(id_tr)
    X_tr = sparse.hstack([w_tr, sparse.csr_matrix(id_scaler.transform(id_tr))]).tocsr()
    X_ca = sparse.hstack([vec.transform([normalise(t) for t in cx]),
                          sparse.csr_matrix(id_scaler.transform(np.stack([id_features(t) for t in cx])))]).tocsr()
    print(f"training rows: {len(ty)} (from {sum(u['split'] == 'train' for u in units)} documents), calibration rows: {len(cy)}, "
          f"features: {X_tr.shape[1]}")
    best = None
    for C in (3, 10, 30, 100, 300):
        clf = LogisticRegression(C=C, max_iter=3000).fit(X_tr, ty)
        nll = _nll(clf.predict_proba(X_ca), cy)
        print(f"  C={C:<4} calib NLL {nll:.3f}")
        if best is None or nll < best[0]:
            best = (nll, C, clf)
    _, C, clf = best
    logits = clf.decision_function(X_ca)
    temps = {}
    for v in VIEWS:
        m = cv == v
        if m.sum() < 10:
            temps[v] = 1.0
            continue

        def nll_t(t, m=m):
            z = logits[m] / t
            z -= z.max(axis=1, keepdims=True)
            p = np.exp(z)
            return _nll(p / p.sum(axis=1, keepdims=True), cy[m])

        temps[v] = float(minimize_scalar(nll_t, bounds=(0.02, 10), method="bounded").x)
        if temps[v] < 0.03:
            print(f"  note: the {v} temperature sits at its lower bound: the calibration split has almost no errors in this view")
    print(f"chosen C={C}; temperature per view: " + ", ".join(f"{v} {t:.2f}" for v, t in temps.items()))
    prior = np.bincount(ty, minlength=len(classes)) / len(ty)
    return TextModel(classes, vec, id_scaler, clf, temps, prior)


def main(text_path: str | None = None) -> None:
    root = DATA_DIR / "sample"
    units = [json.loads(line) for line in open(text_path or root / "text.jsonl")]
    labels = {r["key"]: r for r in csv.DictReader(open(root / "labels.csv"))}
    classes = model_class_ids()
    buckets = bucket_of()
    merged = tuple(model_merge())

    model = train(units, classes)
    joblib.dump(model, DATA_DIR / "models" / "l2.joblib")

    # Text alone, per reading depth, on dev-test.
    dev = [u for u in units if u["split"] == "dev_test"]
    print("\ntext alone on dev-test (accuracy over the 15 model classes, documents that have that view):")
    by_view = {}
    for v in VIEWS:
        us = [u for u in dev if v in views_of(u)]
        if not us:
            continue
        p = model.proba([view_text(u, v) for u in us], v)
        y = np.array([classes.index(to_model_class(u["cls"])) for u in us])
        by_view[v] = {"n": len(us), "accuracy": float(np.mean(p.argmax(1) == y)), "settled_95": float(np.mean(p.max(1) >= THRESHOLD))}
        print(f"  {v:7} n={len(us):4}  accuracy {by_view[v]['accuracy']:.3f}  confident >= 95%: {by_view[v]['settled_95']:.1%}")

    print("\ndiscriminator table (weight gap w_A - w_B; letter pieces are of the normalised text):")
    table = {}
    for a, b in PAIRS:
        d = model.discriminators(a, b, k=10)
        table[f"{a} vs {b}"] = d
        print(f"  {a:>20}: " + ", ".join(n for n, _ in d[a][:8]))
        print(f"  {b:>20}: " + ", ".join(n for n, _ in d[b][:8]))
    json.dump(table, open(root / "l2_discriminators.json", "w"), indent=1)

    # The address question (D24), on KYC documents.
    kyc = [u for u in units if to_model_class(u["cls"]) in merged]
    tr = [u for u in kyc if u["split"] == "train"]
    check = AddressCheck.fit([address_text(u) for u in tr], [u["cls"] == "proof_of_address" for u in tr])
    joblib.dump(check, DATA_DIR / "models" / "address.joblib")
    kd = [u for u in kyc if u["split"] == "dev_test"]
    lv_by_sub = defaultdict(Counter)
    conf = Counter()
    for u in kd:
        fmt = "PDF" if "#" in u["unit"] else u["fmt"]
        pa = check.p_address(address_text(u), poa_share(fmt))
        pred = "proof_of_address" if pa >= 0.5 else "proof_of_identity"
        conf[(u["cls"], pred)] += 1
        lv_by_sub[u["subtype"]][LEVELS[level(address_text(u))]] += 1
    poa_rec = conf[("proof_of_address", "proof_of_address")] / max(sum(v for k, v in conf.items() if k[0] == "proof_of_address"), 1)
    poi_rec = conf[("proof_of_identity", "proof_of_identity")] / max(sum(v for k, v in conf.items() if k[0] == "proof_of_identity"), 1)
    print(f"\naddress question on dev-test KYC documents (n={len(kd)}), text from a full read: "
          f"PoA recall {poa_rec:.3f}, PoI recall {poi_rec:.3f}")
    print("  levels P(level | PoA):", np.round(check.lik_poa, 3).tolist(), " P(level | PoI):", np.round(check.lik_poi, 3).tolist())
    for sub, c in sorted(lv_by_sub.items()):
        print(f"  {sub:24} " + ", ".join(f"{k}: {v}" for k, v in c.most_common()))

    # The combined path on dev-test.
    pages = np.load(root / "pages.npz")
    l1 = joblib.load(DATA_DIR / "models" / "l1.joblib")
    page_row = {(k, int(p)): i for i, (k, p) in enumerate(zip(pages["key"], pages["page"]))}
    bench = json.load(open(DATA_DIR / "bench.json"))

    def start_page(u):
        if "#" not in u["unit"]:
            return 0
        key, j = u["unit"].split("#")
        return json.loads(labels[key]["segments"])[int(j)]["start"] - 1

    records = []
    # dev-test is scored; calib runs the same path so L3 can be calibrated on it (D25, 4c)
    for u in [u for u in units if u["split"] in ("calib", "dev_test")]:
        row = page_row.get((u["key"], start_page(u)))
        l1_lik = l1.likelihood(pages["feats"][[row]])[0] if row is not None else None
        records.append(run_to_l2(u, l1_lik, model, check, buckets, merged))

    calib_records = records
    records = [r for r in records if r["split"] == "dev_test"]
    scored = class_ids(scored_only=True)
    y_true = [r["cls"] for r in records]
    y_pred = [r["pred"] for r in records]
    bar = meets_bar(y_true, y_pred, scored, critical_classes())
    settled = [r for r in records if r["pred"] != ABSTAIN]
    acc = np.mean([r["pred"] == r["cls"] for r in settled])
    rec_settled = {c: np.mean([r["pred"] == c for r in settled if r["cls"] == c]) for c in critical_classes()}
    print(f"\nL0 + L1 + L2 + address question on dev-test (n={len(records)} documents and bundle segments):")
    print(f"  settled: {len(settled) / len(records):.1%} at accuracy {acc:.3f}; on to L3: {1 - len(settled) / len(records):.1%}")
    print(f"  macro-F1, L3 cases counted as errors: {bar['macro_f1_abstain_as_error']:.3f}; L3 cases left out: {bar['macro_f1_abstain_excluded']:.3f}")
    print("  critical recall, L3 cases counted as misses: " + ", ".join(f"{c} {v:.3f}" for c, v in bar["critical_recall"].items()))
    print("  critical recall among settled documents:     " + ", ".join(f"{c} {v:.3f}" for c, v in rec_settled.items()))

    stops = ["native text", "native + L1", "L1", "selective read", "full page", "more pages", "address question", "address unsure", "to L3"]
    print("\nwhere documents stop, by bucket (share of the bucket's dev-test documents):")
    print(f"  {'bucket':16}" + "".join(f"{s[:13]:>14}" for s in stops))
    for b in list(load("classes")["buckets"]):
        rs = [r for r in records if r["bucket"] == b]
        if rs:
            c = Counter(r["stop"] for r in rs)
            print(f"  {b:16}" + "".join(f"{c[s] / len(rs):>14.0%}" for s in stops) + f"   n={len(rs)}")
    errors = Counter((r["cls"], r["pred"]) for r in settled if r["pred"] != r["cls"])
    print("\nerrors among settled (true -> predicted):", errors.most_common(8))
    to_l3 = Counter(r["cls"] for r in records if r["pred"] == ABSTAIN)
    print("sent on to L3, by true class:", to_l3.most_common())

    # Cost of L2's reading at 5M, by class mix, at the bench's per-read rates.
    mix = load("class_mix")["classes"]
    n_docs = load("brief")["n_documents"]
    # Bench rates per read, scaled by how long this class's reads took relative to all reads
    # (an ID card has far fewer lines than an A4 page).
    med = {k: np.median([u[f"{k}_s"] for u in units if u[f"{k}_s"] > 0]) for k in ("sel", "full1")}
    cost = Counter()
    l3_docs = 0.0
    for c, spec in mix.items():
        rs = [r for r in records if r["cls"] == c]
        if not rs:
            continue
        share = spec["share"] / 100 * n_docs
        all_c = [u for u in units if u["cls"] == c]
        scale = {k: (np.median([u[f"{k}_s"] for u in all_c if u[f"{k}_s"] > 0] or [med[k]]) / med[k]) for k in ("sel", "full1")}
        rate = {"sel": bench["ocr_selective_s"] * scale["sel"], "full1": bench["ocr_full_s"] * scale["full1"]}
        for k in ("sel", "full1"):
            cost[k] += share * np.mean([r[k] for r in rs]) * rate[k]
        cost["more"] += share * np.mean([r["more"] * max(r["n_more"], 1) for r in rs]) * bench["ocr_full_s"]
        l3_docs += share * np.mean([r["pred"] == ABSTAIN for r in rs])
    inr = {k: v * INR_PER_CORE_S for k, v in cost.items()}
    total = sum(inr.values())
    print(f"\nL2 reading at 5M (bench rates, class mix from class_mix.yaml): selective Rs {inr['sel']:,.0f}, "
          f"full page Rs {inr['full1']:,.0f}, more pages Rs {inr['more']:,.0f}; total Rs {total:,.0f} on this Mac, "
          f"Rs {2 * total:,.0f} on a 2x slower cloud vCPU")
    print(f"documents going on to L3 at 5M: about {l3_docs:,.0f} ({l3_docs / n_docs:.1%})")
    kyc_full = [r["full1_s"] for r in records if r["cls"] in ("proof_of_identity", "proof_of_address") and r["full1_s"] > 0]
    other_full = [r["full1_s"] for r in records if r["cls"] not in ("proof_of_identity", "proof_of_address") and r["full1_s"] > 0]
    print(f"measured full read, CPU s: KYC cards {np.median(kyc_full):.2f} median, other pages {np.median(other_full):.2f} "
          f"(5 workers sharing 6 cores, so slower than the single-core bench)")

    json.dump({"by_view": by_view, "address": {"poa_recall": poa_rec, "poi_recall": poi_rec, "n": len(kd)},
               "settled": len(settled) / len(records), "settled_accuracy": float(acc), **bar,
               "critical_recall_settled": {c: float(v) for c, v in rec_settled.items()},
               "cost_inr_mac": inr, "cost_inr_total_mac": total, "l3_docs_5m": l3_docs},
              open(root / "l2_metrics.json", "w"), indent=1, default=float)
    with open(root / "l2_predictions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(calib_records[0]))
        w.writeheader()
        w.writerows(calib_records)


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
