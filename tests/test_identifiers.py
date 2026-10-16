import random

from common import identifiers as ids


def test_verhoeff_known_value():
    # Standard worked example: the check digit for 236 is 3.
    assert ids.verhoeff_check_digit("236") == 3
    assert ids.verhoeff_valid("2363")
    assert not ids.verhoeff_valid("2364")


def test_fake_aadhaar_validates_and_single_digit_errors_fail():
    rng = random.Random(0)
    for _ in range(200):
        a = ids.fake_aadhaar(rng)
        assert ids.is_aadhaar(a)
        wrong = a[:5] + str((int(a[5]) + 1) % 10) + a[6:]
        assert not ids.is_aadhaar(wrong)


def test_gstin_known_value():
    # A GSTIN widely used as a format example.
    assert ids.gstin_check_char("27AAPFU0939F1Z") == "V"
    assert ids.is_gstin("27AAPFU0939F1ZV")
    assert not ids.is_gstin("27AAPFU0939F1ZW")


def test_fake_gstin_and_pan():
    rng = random.Random(1)
    for _ in range(200):
        g = ids.fake_gstin(rng)
        assert ids.is_gstin(g)
        assert ids.is_pan(g[2:12])


def test_mrz_check_digits_icao_specimen():
    # ICAO 9303 specimen passport: document number, birth date, expiry date.
    assert ids.mrz_check_digit("L898902C<") == 3
    assert ids.mrz_check_digit("690806") == 1
    assert ids.mrz_check_digit("940623") == 6


def test_ifsc_format():
    rng = random.Random(2)
    assert ids.IFSC_RE.fullmatch(ids.fake_ifsc(rng))
