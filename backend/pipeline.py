"""
pipeline.py

Orchestrates the full Kavach flow for one call:

    transcript chunks -> stage classifier -> sequence-aware risk engine -> events

In production this sits downstream of real-time speech-to-text (Faster-Whisper
in the architecture described in the deck); this module is deliberately
decoupled from audio/STT so it can be:
  (a) driven live from a real STT stream,
  (b) driven from a pre-written test script for offline evaluation, or
  (c) driven from the demo dashboard's "replay" button.

Every call to `process_chunk` returns a structured event describing exactly
what changed and why -- this is what makes the risk score explainable rather
than a black-box number.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, List

from embeddings import get_matcher
from risk_engine import RiskEngine


@dataclass
class ChunkEvent:
    chunk_index: int
    text: str
    matched_stage: Optional[str]
    confidence: float
    matched_reference: Optional[str]
    new_stage_fired: bool
    score: int
    tier: str
    fired_stages: List[str]


class KavachPipeline:
    def __init__(self, backend: str = "lite"):
        self.matcher = get_matcher(backend=backend)
        self.engine = RiskEngine()
        self._chunk_index = 0

    def process_chunk(self, text: str) -> ChunkEvent:
        self._chunk_index += 1
        result = self.matcher.classify(text)

        before = set(self.engine.state.fired_stages)
        state = self.engine.ingest(result.stage, result.confidence)
        after = set(state.fired_stages)
        new_stage_fired = len(after) > len(before)

        return ChunkEvent(
            chunk_index=self._chunk_index,
            text=text,
            matched_stage=result.stage,
            confidence=round(result.confidence, 3),
            matched_reference=result.matched_reference,
            new_stage_fired=new_stage_fired,
            score=state.score,
            tier=state.tier,
            fired_stages=list(state.fired_stages),
        )

    def run_script(self, lines: List[str]) -> List[ChunkEvent]:
        """Convenience helper: feed a whole pre-written script through the
        pipeline line by line (used by the test harness and by the demo
        server's replay mode)."""
        return [self.process_chunk(line) for line in lines]

    def summary(self) -> dict:
        d = asdict(self.engine.state) if False else self.engine.state.as_dict()
        d["financial_demand_position"] = self.engine.reached_financial_demand_stage_index()
        d["total_chunks"] = self._chunk_index
        return d
