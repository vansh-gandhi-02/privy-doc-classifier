from common.config import bucket_of, class_ids, class_of_subtype, critical_classes, load
from docgen.plan import class_weights, plan
from scripts.check_mix import problems


def test_every_subtype_maps_to_a_known_class():
    classes = set(class_ids())
    assert set(class_of_subtype().values()) <= classes


def test_every_class_has_a_subtype_and_a_bucket():
    assert set(class_ids()) == set(class_of_subtype().values())
    buckets = set(load("classes")["buckets"])
    assert set(bucket_of().values()) <= buckets


def test_class_mix_covers_every_class():
    assert set(load("class_mix")["classes"]) == set(class_ids())


def test_every_class_format_has_a_subtype_that_can_produce_it():
    subtypes = load("subtypes")["subtypes"]
    for c, spec in load("class_mix")["classes"].items():
        for fmt in spec["formats"]:
            if fmt == "EML":
                continue  # any class can be an email attachment (D12)
            assert any(s["class"] == c and fmt in s["formats"] for s in subtypes.values()), (c, fmt)


def test_class_mix_matches_brief():
    assert problems() == []


def test_plan_meets_minimum_per_class():
    p = plan()
    cfg = load("sample")
    assert sum(p["core"].values()) == cfg["core_size"]
    for c in class_ids():
        total = sum(n for part in p.values() for (cc, _), n in part.items() if cc == c)
        assert total >= cfg["min_per_class"]
    assert all(w > 0 for w in class_weights(p).values())


def test_critical_classes_are_scored():
    scored = set(class_ids(scored_only=True))
    assert set(critical_classes()) <= scored
