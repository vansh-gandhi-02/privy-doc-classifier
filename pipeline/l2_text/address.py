"""The address question (walkthrough step 3, DECISIONS D24).

L1 and L2 only decide "is this a KYC ID document?". Every document that lands
there is then asked one question: is an address visible? Yes gives Proof of
Address, no gives Proof of Identity (the D3 rule, asked directly).

An address means a valid PIN code plus an address label ("Address", S/O, C/O)
or a state name. A passport data page's "Place of Birth: PUNE, MAHARASHTRA" has a
state but no PIN, so it is not an address. The text comes from a full read of
the card (option A, D24): the address is rarely in the top or largest lines, so
the selective read would miss it.

The check gives a level 0-3. How often each level occurs on PoI and on PoA
documents is counted on the training split, so the rule's evidence is
calibrated, then combined with the prior share of PoA among KYC documents for
the file's format.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from pipeline.l2_text.features import normalise

_PIN = re.compile(r"(?<![\d/])[1-9]\d{5}(?![\d/])")  # not inside a date: OCR runs "14/09/202514/09/2035" together
_LABEL = re.compile(r"address|\b[SDWC]\s?/\s?O\b", re.I)
# All 28 states and 8 union territories, spaces removed (see textfeat.normalise).
STATES = ["andhrapradesh", "arunachalpradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana", "himachalpradesh",
          "jharkhand", "karnataka", "kerala", "madhyapradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
          "odisha", "punjab", "rajasthan", "sikkim", "tamilnadu", "telangana", "tripura", "uttarpradesh", "uttarakhand",
          "westbengal", "andamanandnicobar", "chandigarh", "dadraandnagarhaveli", "damananddiu", "delhi", "jammuandkashmir",
          "ladakh", "lakshadweep", "puducherry"]
LEVELS = ["none", "label or state only", "PIN + state", "PIN + label"]


def level(text: str) -> int:
    pin, label = bool(_PIN.search(text)), bool(_LABEL.search(text))
    norm = normalise(text)
    state = any(s in norm for s in STATES)
    if pin and label:
        return 3
    if pin and state:
        return 2
    if label or state:
        return 1
    return 0


@dataclass
class AddressCheck:
    """P(level | PoA) and P(level | PoI), counted on the training split."""
    lik_poa: np.ndarray
    lik_poi: np.ndarray

    @classmethod
    def fit(cls, texts: list[str], is_poa: list[bool]) -> AddressCheck:
        counts = np.ones((2, len(LEVELS)))  # add-one smoothing
        for t, y in zip(texts, is_poa):
            counts[int(y), level(t)] += 1
        counts /= counts.sum(axis=1, keepdims=True)
        return cls(lik_poa=counts[1], lik_poi=counts[0])

    def p_address(self, text: str, prior_poa: float) -> float:
        lv = level(text)
        a, b = prior_poa * self.lik_poa[lv], (1 - prior_poa) * self.lik_poi[lv]
        return float(a / (a + b))
