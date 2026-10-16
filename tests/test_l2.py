import random

import pytest

from common import identifiers as ids
from common.config import bucket_of, class_ids, model_class_ids, to_model_class, to_model_dist
from pipeline.l2_text.address import AddressCheck, level
from pipeline.posterior import Posterior
from pipeline.l0_open.metadata import model_prior_for, poa_share
from pipeline.l2_text.features import ID_NAMES, id_features, normalise


def _f(text: str) -> dict[str, float]:
    return dict(zip(ID_NAMES, id_features(text)))


def test_normalise_ignores_ocr_spacing_and_case():
    assert normalise("Senior Secondary 2024") == normalise("SENIORSECONDARY 1999") == "seniorsecondary0000"


def test_aadhaar_checksum_separates_valid_from_typo():
    rng = random.Random(1)
    a = ids.fake_aadhaar(rng)
    typo = a[:-1] + str((int(a[-1]) + 1) % 10)
    assert _f(f"Aadhaar {a}")["aadhaar_valid"] > 0 and _f(f"Aadhaar {a}")["aadhaar_pattern"] == 0
    assert _f(f"Aadhaar {typo}")["aadhaar_pattern"] > 0 and _f(f"Aadhaar {typo}")["aadhaar_valid"] == 0
    assert _f("Aadhaar No. XXXX XXXX 1234")["aadhaar_masked"] > 0


def test_pan_holder_type_and_ids_per_line():
    rng = random.Random(2)
    person, company = ids.fake_pan(rng, "P"), ids.fake_pan(rng, "C")
    f = _f(f"PAN {person}\nPAN {company}\nName\nAddress\n")
    assert f["pan_person"] > 0 and f["pan_entity"] > 0
    assert f["ids_per_line"] == pytest.approx(2 / 4)


def test_address_levels():
    assert level("Address: S/O Ramesh, Flat 12, Baner Road, Pune, Maharashtra - 411045") == 3
    assert level("Kothrud, Pune, Maharashtra 411038") == 2
    assert level("Place of Birth: PUNE, MAHARASHTRA") == 1   # a state but no PIN: not an address
    assert level("INCOME TAX DEPARTMENT ABCPE1234F") == 0


def test_address_check_combines_level_evidence_with_prior():
    check = AddressCheck.fit(["Address: Pune, Maharashtra 411001"] * 20 + ["Name DOB"] * 20, [True] * 20 + [False] * 20)
    assert check.p_address("Address: Kothrud, Pune 411038", 0.4) > 0.9
    assert check.p_address("GOVERNMENT OF INDIA Name DOB", 0.4) < 0.1


def test_poi_and_poa_merge_for_the_models_only():
    assert "kyc_id" in model_class_ids() and "proof_of_identity" not in model_class_ids()
    assert len(model_class_ids()) == len(class_ids()) - 1
    assert to_model_class("proof_of_address") == "kyc_id" and bucket_of()["kyc_id"] == "kyc"
    p = model_prior_for("JPG")
    assert sum(p.values()) == pytest.approx(1.0)
    assert to_model_dist({"proof_of_identity": 0.12, "proof_of_address": 0.08, "itr": 0.8})["kyc_id"] == pytest.approx(0.2)
    assert poa_share("JPG") == pytest.approx(8 / 20)


def test_merged_class_waits_for_the_address_question():
    post = Posterior.from_prior({"kyc_id": 0.97, "itr": 0.03}, needs_split=("kyc_id",))
    d = post.decide(0.95, {"kyc_id": "kyc", "itr": "personal_income"})
    assert d.action == "lock_bucket" and d.bucket == "kyc"
    post.split("kyc_id", {"proof_of_address": 0.99, "proof_of_identity": 0.01})
    d = post.decide(0.95, {"kyc_id": "kyc", "itr": "personal_income", "proof_of_address": "kyc", "proof_of_identity": "kyc"})
    assert d.action == "accept" and d.label == "proof_of_address"
    assert sum(post.label_probs().values()) == pytest.approx(1.0)


def test_masker_hides_ids_but_keeps_classification_cues():
    from pipeline.l3_llm.llm import mask
    t = mask("PAN ABCPE1234F Aadhaar XXXX XXXX 5678 Card 4111 1111 1111 1111 Ph +91 98765 43210 "
             "DOB 14/08/2002 Pune - 411045 Loan Amount Rs. 5,00,000 Assessment Year 2023-24")
    for leaked in ("ABCPE1234F", "5678", "4111", "98765", "14/08/2002", "411045"):
        assert leaked not in t
    for kept in ("[PAN_PERSON]", "[AADHAAR_MASKED]", "[CARD_NO]", "Loan Amount", "Assessment Year 2023-24"):
        assert kept in t


def test_candidates_cover_99_percent_of_real_classes():
    from pipeline.l3_llm.llm import candidates
    assert candidates({"loan_application": 0.6, "cc_application": 0.39, "itr": 0.004, "other": 0.006}) == ["loan_application", "cc_application"]
    assert len(candidates({c: 0.1 for c in ["itr", "gst", "salary_slip", "bank_statement", "cc_statement", "legal_contract", "property_collateral"]})) == 5


def test_controller_moves_the_gate_the_right_way():
    from pipeline.controller import BudgetController, gate_for
    over = BudgetController(target_inr=100, total_docs=100)
    assert over.adjust(50, spent_inr=80) < 0.95          # over plan: accept more at L2
    under = BudgetController(target_inr=100, total_docs=100)
    assert under.adjust(50, spent_inr=20) > 0.95         # under plan: buy accuracy
    assert 0.85 <= over.threshold and under.threshold <= 0.99
    assert gate_for(0.85, critical_prob=0.2) == 0.95     # the critical safety net
    assert gate_for(0.85, critical_prob=0.01) == 0.85
