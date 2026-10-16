"""Gates and the budget controller (walkthrough steps 6 and 7).

The brief requires the system to notice mid-run when it is trending over or
under budget and change its own behaviour.

The gate (D9): a document is accepted when one class reaches the threshold.
The controller moves one threshold only, the one at the L2 -> L3 gate (tau):
- documents at or above tau after L2 are accepted without the LLM
- documents below it go to L3 (and on to L4 if still unsure)
L1's own gate and the gate after L3 stay at 95%.

Critical safety net (step 6): if a document has at least a 10% chance of being a
critical class (Legal, Property, PoI, PoA, D7), its own gate never drops below
95%, whatever the controller does. Cheap mistakes are allowed on ordinary
classes, never on critical ones.

The controller (step 7) compares spend with a straight plan line from 0 to the
target and nudges tau after every batch. Spending ahead of plan lowers tau
(more documents accepted at L2, fewer LLM calls); behind plan raises it (buys
accuracy with the spare budget) only if the LLM is measured to beat L2 on the
documents that raising tau would add; otherwise it only recovers back to 95% and the
unspent budget stays as margin (value of information, D28). The step is proportional to how far off plan
spend is, and to the room left before the limit (0.85 or 0.99), so tau never
jumps to an end. A reserve (10%, budget.yaml) is kept out of the target.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL_NET = 0.10
BASE_THRESHOLD = 0.95


def gate_for(tau: float, critical_prob: float) -> float:
    """The L2 -> L3 threshold for one document: tau, floored at 95% for possibly-critical documents."""
    return max(tau, BASE_THRESHOLD) if critical_prob >= CRITICAL_NET else tau


@dataclass
class BudgetController:
    target_inr: float
    total_docs: int
    threshold: float = BASE_THRESHOLD
    min_threshold: float = 0.85
    max_threshold: float = 0.99
    gain: float = 0.5
    allow_raise: bool = True   # raise tau only if the extra LLM calls buy accuracy (D28)
    history: list[tuple[int, float, float, float]] = field(default_factory=list)  # docs, spent, planned, tau

    def planned_spend(self, docs_done: int) -> float:
        return self.target_inr * docs_done / self.total_docs

    def adjust(self, docs_done: int, spent_inr: float) -> float:
        planned = self.planned_spend(docs_done)
        if planned > 0:
            off = max(min((planned - spent_inr) / planned, 1.0), -1.0)   # + under plan, - over plan
            ceiling = self.max_threshold if self.allow_raise else max(BASE_THRESHOLD, self.threshold)
            room = (ceiling - self.threshold) if off > 0 else (self.threshold - self.min_threshold)
            self.threshold = min(max(self.threshold + self.gain * off * room, self.min_threshold), ceiling)
        self.history.append((docs_done, spent_inr, planned, self.threshold))
        return self.threshold
