"""Text features for L2 (walkthrough step 3, DECISIONS D23).

Two kinds:
- letter pieces: the text is lower-cased, digits become 0, and everything that
  is not a letter or digit is dropped, so "Senior Secondary", "SENIOR SECONDARY"
  and OCR's "SENIORSECONDARY" all give the same 3-5 letter pieces
- ID evidence: for each Indian identifier, how many appear with a valid
  checksum and how many only match the pattern (often an OCR typo), plus
  context: how many lines, how many distinct ID types, IDs per line. A card has
  one ID in a few lines; a form has several among many lines.

IDs are evidence, not verdicts: the model learns how much more often each one
appears under one class than another, the same way it learns words.
"""
from __future__ import annotations

import math
import re

import numpy as np

from common import identifiers as ids

_NON_ALNUM = re.compile(r"[^a-z0]+")
_DIGIT = re.compile(r"\d")


def normalise(text: str) -> str:
    return _NON_ALNUM.sub("", _DIGIT.sub("0", text.lower()))


_CARD_MASKED = re.compile(r"(?:[X\*]{4}[\s-]?){3}\d{4}\b|\b\d{4}[\s-]?(?:[X\*]{4}[\s-]?){2}\d{4}\b", re.I)
_AADHAAR_MASKED = re.compile(r"[X\*]{4}\s?[X\*]{4}\s?\d{4}\b", re.I)
_EPIC = re.compile(r"\b[A-Z]{3}\d{7}\b")
_DL = re.compile(r"\b[A-Z]{2}[- ]?\d{2}[- ]?(?:19|20)\d{2}\d{7}\b")
_MRZ = re.compile(r"P<[A-Z]{3}|<<<")
_MRZ_LINE2 = re.compile(r"([A-Z0-9<]{9})(\d)[A-Z]{3}\d{6}")
_UDIN = re.compile(r"\b\d{8}[A-Z0-9]{10}\b")
_CIN = re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
_PIN = re.compile(r"(?<![\d/])[1-9]\d{5}(?![\d/])")  # not inside a date: OCR runs "14/09/202514/09/2035" together

ID_TYPES = ["aadhaar_valid", "aadhaar_pattern", "aadhaar_masked", "card_masked", "pan_person", "pan_entity", "gstin_valid",
            "gstin_pattern", "ifsc", "mrz", "mrz_valid", "passport_no", "voter_epic", "dl_no", "udin", "cin"]
ID_NAMES = ID_TYPES + ["pin_code", "log_lines", "id_types", "ids_per_line"]


def id_features(text: str) -> np.ndarray:
    t = text.upper()
    c = dict.fromkeys(ID_NAMES, 0.0)
    for m in ids.AADHAAR_RE.finditer(t):
        digits = re.sub(r"\s", "", m.group())
        c["aadhaar_valid" if ids.verhoeff_valid(digits) else "aadhaar_pattern"] += 1
    c["card_masked"] = len(_CARD_MASKED.findall(t))
    c["aadhaar_masked"] = len(_AADHAAR_MASKED.findall(_CARD_MASKED.sub(" ", t)))  # a masked card ends like a masked Aadhaar
    for m in ids.PAN_RE.finditer(t):
        c["pan_person" if m.group()[3] == "P" else "pan_entity"] += 1
    for m in ids.GSTIN_RE.finditer(t):
        c["gstin_valid" if ids.is_gstin(m.group()) else "gstin_pattern"] += 1
    c["ifsc"] = len(ids.IFSC_RE.findall(t))
    c["mrz"] = len(_MRZ.findall(t))
    c["mrz_valid"] = sum(ids.mrz_check_digit(m.group(1)) == int(m.group(2)) for m in _MRZ_LINE2.finditer(t))
    c["passport_no"] = len(ids.PASSPORT_NO_RE.findall(t))
    c["voter_epic"] = len(_EPIC.findall(t))
    c["dl_no"] = len(_DL.findall(t))
    c["udin"] = sum(any(ch.isalpha() for ch in m) for m in _UDIN.findall(t))
    c["cin"] = len(_CIN.findall(t))
    c["pin_code"] = len(_PIN.findall(t))
    lines = max(sum(1 for ln in text.splitlines() if ln.strip()), 1)
    n_ids = sum(c[k] for k in ID_TYPES)
    out = [math.log1p(c[k]) for k in ID_TYPES + ["pin_code"]]
    out += [math.log(lines), float(sum(c[k] > 0 for k in ID_TYPES)), n_ids / lines]
    return np.array(out, dtype=np.float32)
