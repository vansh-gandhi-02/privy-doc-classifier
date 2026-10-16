"""Indian document identifiers: generate valid fakes, and validate what OCR finds.

Used in two places. The generator stamps realistic numbers into synthetic
documents, and L2 uses the validators as high-precision evidence: a 12-digit
number that passes the Verhoeff check is very likely an Aadhaar number, while a
random 12-digit string passes only 1 time in 10.

Fakes are random digits attached to fake names. They are not derived from, or
checked against, any real person's identifiers.
"""
from __future__ import annotations

import random
import re
import string

# Verhoeff check digit (dihedral group D5), used by Aadhaar.
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_check_digit(digits: str) -> int:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return _INV[c]


def verhoeff_valid(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


# Aadhaar: 12 digits, first digit 2-9, last digit a Verhoeff check digit.
# Printed as "1234 5678 9012"; masked copies show only the last 4 digits.
AADHAAR_RE = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")


def fake_aadhaar(rng: random.Random) -> str:
    body = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(10))
    return body + str(verhoeff_check_digit(body))


def is_aadhaar(text: str) -> bool:
    digits = re.sub(r"\s", "", text)
    return bool(re.fullmatch(r"[2-9]\d{11}", digits)) and verhoeff_valid(digits)


# PAN: AAAPA1234A. The 4th letter is the holder type (P person, C company, F firm,
# H HUF...), the 5th is the first letter of the surname or entity name. The last
# letter is a check letter whose algorithm is not public, so fakes use a random one.
PAN_HOLDER_TYPES = "PCHFATBLJG"
PAN_RE = re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]\b")


def fake_pan(rng: random.Random, holder_type: str = "P", name_initial: str | None = None) -> str:
    letters = string.ascii_uppercase
    initial = (name_initial or rng.choice(letters)).upper()
    return (
        "".join(rng.choice(letters) for _ in range(3))
        + holder_type
        + initial
        + f"{rng.randint(0, 9999):04d}"
        + rng.choice(letters)
    )


def is_pan(text: str) -> bool:
    return bool(PAN_RE.fullmatch(text.strip().upper()))


# GSTIN: 2-digit state code + the holder's PAN + entity number + "Z" + check character.
_GST_CHARS = string.digits + string.ascii_uppercase
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = _GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _GST_CHARS[(36 - total % 36) % 36]


def fake_gstin(rng: random.Random, state_code: str | None = None, pan: str | None = None) -> str:
    state = state_code or f"{rng.randint(1, 37):02d}"
    pan = pan or fake_pan(rng, holder_type=rng.choice("CFP"))
    first14 = state + pan + rng.choice("123456789") + "Z"
    return first14 + gstin_check_char(first14)


def is_gstin(text: str) -> bool:
    t = text.strip().upper()
    return bool(GSTIN_RE.fullmatch(t)) and gstin_check_char(t[:14]) == t[14]


# IFSC: 4-letter bank code, a zero, then a 6-character branch code.
BANK_CODES = {
    "SBIN": "State Bank of India",
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank",
    "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda",
    "CNRB": "Canara Bank",
    "UBIN": "Union Bank of India",
    "YESB": "Yes Bank",
    "INDB": "IndusInd Bank",
    "IDIB": "Indian Bank",
}
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")


def fake_ifsc(rng: random.Random, bank_code: str | None = None) -> str:
    code = bank_code or rng.choice(list(BANK_CODES))
    return code + "0" + "".join(rng.choice(string.digits) for _ in range(6))


# Passport: Indian passport numbers are a letter and 7 digits. The data page's
# machine-readable zone (MRZ) carries ICAO 9303 check digits, weights 7, 3, 1.
PASSPORT_NO_RE = re.compile(r"\b[A-Z][0-9]{7}\b")


def mrz_check_digit(field: str) -> int:
    def value(ch: str) -> int:
        if ch.isdigit():
            return int(ch)
        if ch == "<":
            return 0
        return ord(ch) - ord("A") + 10

    weights = (7, 3, 1)
    return sum(value(ch) * weights[i % 3] for i, ch in enumerate(field)) % 10


def fake_passport_no(rng: random.Random) -> str:
    return rng.choice(string.ascii_uppercase) + f"{rng.randint(0, 9_999_999):07d}"


# PIN code: 6 digits, first digit 1-9. A PIN code near the word "Address" is the
# cheapest address detector for the PoI vs PoA rule (DECISIONS D3).
PIN_RE = re.compile(r"\b[1-9]\d{5}\b")
