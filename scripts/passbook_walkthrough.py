"""The interviewer's passbook point, worked through with the Posterior class.

A phone photo of a passbook page. Likelihoods are illustrative, not measured.
Watch step L2: the header keywords push "passbook" over 95%, but only by
ruling out everything else. The statement-to-passbook ratio does not move,
because those keywords are equally likely on both.

Run: python -m scripts.passbook_walkthrough
"""
from __future__ import annotations

from pipeline.posterior import Posterior

PRIOR = {"statement": 0.13, "cc_statement": 0.04, "passbook": 0.02, "everything_else": 0.81}

STEPS = [
    ("L0 format is JPG", {"statement": 0.05, "cc_statement": 0.01, "passbook": 0.70, "everything_else": 0.18}),
    ("L1 booklet page, dot-matrix", {"statement": 0.05, "cc_statement": 0.02, "passbook": 0.80, "everything_else": 0.05}),
    ("L2 header: cust ID, branch", {"statement": 0.90, "cc_statement": 0.30, "passbook": 0.90, "everything_else": 0.01}),
]


def run() -> Posterior:
    post = Posterior.from_prior(PRIOR)
    for step, lik in STEPS:
        post.update(step, lik)
    return post


def main() -> None:
    post = run()
    print(f"{'step':30}" + "".join(f"{c:>16}" for c in post.classes) + f"{'stmt/passbook':>15}")
    for step, probs in post.history:
        print(f"{step:30}" + "".join(f"{p:>16.1%}" for p in probs) + f"{probs[0] / probs[2]:>15.3f}")
    print(f"\nDecision at 95%: {post.decide(0.95)}")


if __name__ == "__main__":
    main()
