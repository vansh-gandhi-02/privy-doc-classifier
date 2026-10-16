"""One document's path through the pipeline, from evidence read once and cached
(page features from scripts/extract_pages.py, text from scripts/extract_text.py).

    prior for the file's format (L0)
    text files: free text (L2) first, then layout (L1) if still unsure (D22)
    scans:      layout (L1), then the reading ladder, each rung replacing the
                last rung's text evidence (D20, D23):
                selective read -> full page -> next and last page
    KYC ID document at 95%: the address question, from a full read (D24)
    still unsure: L3, the LLM (D25); then L4, a human

Used by scripts/train_l2.py on the dev sample and by scripts/run_final.py on the
lockbox, so both run exactly the same code.
"""
from __future__ import annotations

import json
from collections import Counter

from evaluation.metrics import ABSTAIN
from common.config import critical_classes
from pipeline.controller import gate_for
from pipeline.posterior import Posterior
from pipeline.l0_open.metadata import model_prior_for, poa_share

THRESHOLD = 0.95
MIN_TEXT = 20
# Reading recipes per bucket (D23, 3c). Legal and property documents open with an
# e-stamp certificate page that contracts and deeds share, so the title that decides
# them is on a later page: read the first, next and last pages before deciding.
RECIPES = {"legal_property": ("more",)}
CRITICAL = set(critical_classes())


def view_text(u: dict, view: str) -> str:
    return u["full1"] + "\n" + u["more"] if view == "more" else u[view]


def views_of(u: dict) -> list[str]:
    out = [v for v in ("native", "sel", "full1") if len(u[v].strip()) >= MIN_TEXT]
    if u["more"].strip():
        out.append("more")
    return out


def address_text(u: dict) -> str:
    return u["native"] if len(u["native"].strip()) >= MIN_TEXT else u["full1"] + "\n" + u["more"]


def llm_text(u: dict) -> str:
    if len(u["native"].strip()) >= MIN_TEXT:
        return u["native"]
    return (u["full1"] + "\n" + u["more"]).strip() or u["sel"]


def run_to_l2(u: dict, l1_lik: dict | None, model, check, buckets: dict, merged: tuple, tau: float = THRESHOLD,
              trace: bool = False) -> dict:
    """L0 -> L1 -> L2 -> address question for one document (or bundle segment).
    Returns the record: label (or ABSTAIN: on to L3), where it stopped, the reads
    it needed, and its final probabilities over the brief's labels.

    tau is the budget controller's gate (D28): it applies to every gate before
    the LLM, because reading, not the LLM, is where most of the money goes. A
    document with a 10% or higher chance of a critical class keeps 95%.

    With trace=True the record also holds "trace": the probabilities after every
    step, for showing how one document moves through the pipeline."""
    fmt = "PDF" if "#" in u["unit"] else u["fmt"]
    post = Posterior.from_prior(model_prior_for(fmt), needs_split=merged)
    reads = Counter()
    trail = [(f"L0: prior for a {fmt}", post.label_probs())]

    def settled(p):
        lp = p.label_probs()
        crit = sum(v for c, v in lp.items() if c in CRITICAL or c in merged)
        gate = gate_for(tau, crit)
        dec = p.decide(gate, buckets)
        top, conf = p.top()
        if dec.action == "accept" or (dec.action == "lock_bucket" and top in merged and conf >= gate):
            return top
        return None

    native = len(u["native"].strip()) >= MIN_TEXT
    stop, label = None, None
    if native:  # free text first (D22), then layout if still unsure
        post.update("L2 native", model.likelihood([u["native"]], "native")[0])
        trail.append(("L2: free text", post.label_probs()))
        label, stop = settled(post), "native text"
        if label is None and l1_lik is not None:
            post.update("L1", l1_lik)
            trail.append(("L1: layout", post.label_probs()))
            reads["l1"] += 1
            label, stop = settled(post), "native + L1"
    else:
        if l1_lik is not None:
            post.update("L1", l1_lik)
            trail.append(("L1: layout", post.label_probs()))
            reads["l1"] += 1
            label, stop = settled(post), "L1"
        base = post.copy()
        rungs = (("sel", "selective read"), ("full1", "full page"), ("more", "more pages"))
        lead = max(post.bucket_probs(buckets).items(), key=lambda kv: kv[1])[0]
        if lead in RECIPES:  # the bucket's reading recipe (D23, 3c): skip rungs that cannot decide it
            wanted = [v for v in RECIPES[lead] if v in views_of(u)] or ["full1"]
            rungs = tuple(r for r in rungs if r[0] in wanted)
            if "more" in wanted:
                reads["full1"] += 1  # the "more" view includes the full first page
        for v, name in rungs:
            if label is not None:
                break
            if v not in views_of(u):
                continue
            post = base.copy()  # each rung replaces the text evidence (D23)
            post.update(f"L2 {v}", model.likelihood([view_text(u, v)], v)[0])
            trail.append((f"L2: {name}", post.label_probs()))
            reads[v] += 1
            label, stop = settled(post), name
    if label in merged:  # the address question (D24, option A: always a full read)
        if not native:
            if not reads["full1"]:
                reads["full1"] += 1
            if u["more"].strip() and not reads["more"]:
                reads["more"] += 1
        pa = check.p_address(address_text(u), poa_share(fmt))
        post.split(label, {"proof_of_address": pa, "proof_of_identity": 1 - pa})
        trail.append(("Address question", post.label_probs()))
        dec = post.decide(THRESHOLD, buckets)
        label = dec.label if dec.action == "accept" else None
        stop = "address question" if label else "address unsure"
    if label is None:
        stop = stop if stop == "address unsure" else "to L3"
    probs = post.label_probs()
    for m in merged:  # not split yet: divide by the prior PoA share, for L3's candidate list
        if m in probs:
            pm, pa = probs.pop(m), poa_share(fmt)
            probs.update({"proof_of_address": pm * pa, "proof_of_identity": pm * (1 - pa)})
    rec = dict(unit=u["unit"], split=u["split"], cls=u["cls"], pred=label or ABSTAIN, stop=stop, bucket=buckets.get(u["cls"], "other"),
                conf=max(probs.values()), probs=json.dumps({k: round(v, 5) for k, v in probs.items()}),
                native=native, l1=reads["l1"], sel=reads["sel"], full1=reads["full1"], more=reads["more"],
                n_more=0 if not u["more"].strip() else (1 if u["n_pages"] == 2 else 2),  # next + last page
                sel_s=u["sel_s"], full1_s=u["full1_s"], more_s=u["more_s"], top=post.top()[0])
    if trace:
        rec["trace"] = trail
    return rec
