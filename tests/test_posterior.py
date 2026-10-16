import pytest

from pipeline.posterior import FLOOR, Posterior
from scripts import passbook_walkthrough as walk


def test_prior_is_never_zero():
    post = Posterior.from_prior({"a": 1.0, "b": 0.0})
    assert post.prob("b") > 0
    # A floored class can recover: one strong piece of evidence brings it level,
    # a second puts it on top. Had the prior been exactly 0, it never could.
    post.update("strong evidence for b", {"a": FLOOR, "b": 1.0})
    assert post.prob("b") == pytest.approx(0.5)
    post.update("more evidence for b", {"a": 0.5, "b": 1.0})
    assert post.top()[0] == "b"


def test_unmentioned_classes_are_unaffected_relative_to_each_other():
    post = Posterior.from_prior({"a": 0.2, "b": 0.3, "c": 0.5})
    post.update("only about c", {"c": 0.1})
    assert post.prob("a") / post.prob("b") == pytest.approx(0.2 / 0.3)


def test_passbook_walkthrough():
    post = walk.run()
    assert post.prob("passbook") == pytest.approx(0.965, abs=0.005)
    # L2's shared keywords leave the statement:passbook ratio unchanged.
    before, after = post.history[-2][1], post.history[-1][1]
    assert before[0] / before[2] == pytest.approx(after[0] / after[2])
    assert post.decide(0.95).action == "accept"


def test_bucket_locks_before_class():
    post = Posterior.from_prior({"class10": 0.58, "class12": 0.40, "pan": 0.02})
    buckets = {"class10": "education", "class12": "education", "pan": "kyc"}
    d = post.decide(0.95, buckets)
    assert d.action == "lock_bucket" and d.bucket == "education"
