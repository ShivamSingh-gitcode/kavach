"""
risk_engine.py

Deterministic, sequence-aware risk engine. Takes a stream of per-chunk stage
classifications (from embeddings.py) and maintains a running, explainable
risk score for the call.

Design goals (matching the architecture described in the pitch deck):
  - Deterministic: same input sequence always produces the same score. No
    generative model / black-box LLM call in this path.
  - Explainable: at any point, the engine can report exactly which stages
    have fired and how much each contributed.
  - Sequence-aware, not sequence-REQUIRED: each stage scores independently
    the moment it first fires, regardless of order (so a scammer who skips
    straight to a threat is still caught). An additional bonus rewards the
    classic textbook order when it happens, as an extra signal -- not a
    requirement.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from reference_phrases import STAGE_WEIGHTS, ORDER_BONUS, RISK_TIERS, STAGES


def tier_for_score(score: int) -> str:
    for name, low, high in RISK_TIERS:
        if low <= score <= high:
            return name
    return "CRITICAL" if score > RISK_TIERS[-1][2] else "LOW"


@dataclass
class RiskState:
    fired_stages: list = field(default_factory=list)   # order in which stages first fired
    score: int = 0
    tier: str = "LOW"

    def as_dict(self):
        return {
            "fired_stages": list(self.fired_stages),
            "score": self.score,
            "tier": self.tier,
            "max_possible": sum(STAGE_WEIGHTS.values()) + ORDER_BONUS,
        }


class RiskEngine:
    """One instance per call. Feed it (stage, confidence) pairs chunk by chunk."""

    CLASSIC_ORDER = ["AUTHORITY", "ISOLATION", "THREAT_URGENCY", "FINANCIAL_DEMAND"]

    def __init__(self):
        self.state = RiskState()
        self._fired_set = set()

    def ingest(self, stage: Optional[str], confidence: float = 0.0) -> RiskState:
        """Update engine state with one classified transcript chunk. `stage`
        may be None (no stage matched this chunk -> no-op, this is normal for
        most of a real conversation)."""
        if stage is None or stage in self._fired_set:
            return self.state

        # first time this stage has fired in this call
        self._fired_set.add(stage)
        self.state.fired_stages.append(stage)
        self.state.score += STAGE_WEIGHTS[stage]

        if self.state.fired_stages == self.CLASSIC_ORDER[: len(self.state.fired_stages)] \
                and len(self.state.fired_stages) == len(self.CLASSIC_ORDER):
            self.state.score += ORDER_BONUS

        self.state.tier = tier_for_score(self.state.score)
        return self.state

    def reached_financial_demand_stage_index(self) -> Optional[int]:
        """Returns the 1-based position at which FINANCIAL_DEMAND fired, or
        None if it never fired. Used by the evaluation harness to check
        whether the engine reached HIGH/CRITICAL *before* the money ask."""
        if "FINANCIAL_DEMAND" in self.state.fired_stages:
            return self.state.fired_stages.index("FINANCIAL_DEMAND") + 1
        return None
