"""
embeddings.py

Pluggable similarity backend for matching a transcript chunk against the
curated reference phrases in reference_phrases.py.

Two backends are provided:

1. LiteMatcher (default, fully offline)
   - Uses scikit-learn's character n-gram TF-IDF + cosine similarity.
   - Runs anywhere with no internet access and no model download.
   - Generalises beyond *exact* keyword matching within the same language
     (handles typos, inflected forms, partial phrase overlap) but does NOT
     bridge different scripts/languages (e.g. it will not, on its own, match
     Hindi "Phone mat kaatna" to English "don't disconnect the call").
   - This is what the test harness in this repo actually runs, so every
     number reported in docs/evaluation_results.md was produced by THIS
     backend, honestly labelled as such.

2. LaBSEMatcher (optional, requires internet + extra dependencies)
   - Wraps sentence-transformers' LaBSE (or multilingual MiniLM) model.
   - Produces true cross-lingual sentence embeddings, so a Hindi phrase and
     its English paraphrase land close together in embedding space even
     though they share no words. This is the backend described in the
     architecture slide and is what a real deployment should use.
   - Only imported if explicitly requested, so the rest of the project has
     zero hard dependency on torch / sentence-transformers / a model
     download.

Usage:
    matcher = get_matcher(backend="lite")   # or backend="labse"
    stage, confidence = matcher.classify(chunk_text)
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from reference_phrases import REFERENCE_PHRASES, STAGES


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)  # keep Devanagari + word chars
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class MatchResult:
    stage: Optional[str]
    confidence: float
    matched_reference: Optional[str]
    all_scores: dict


class LiteMatcher:
    """Offline character n-gram TF-IDF cosine-similarity matcher."""

    # Below this cosine-similarity score, we say "no stage matched" rather
    # than force a guess. Tuned empirically on the sample scripts in
    # data/test_scripts/ -- see docs/evaluation_results.md for the confidence
    # distributions this value was chosen from, and honest caveats about
    # what a char n-gram TF-IDF backend can and cannot distinguish.
    THRESHOLD = 0.45

    def __init__(self):
        self._stage_of_ref = []
        corpus = []
        for stage in STAGES:
            for _lang, phrase in REFERENCE_PHRASES[stage]:
                corpus.append(_normalize(phrase))
                self._stage_of_ref.append((stage, phrase))

        self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self._ref_matrix = self._vectorizer.fit_transform(corpus)

    def classify(self, chunk_text: str) -> MatchResult:
        if not chunk_text or not chunk_text.strip():
            return MatchResult(None, 0.0, None, {})

        vec = self._vectorizer.transform([_normalize(chunk_text)])
        sims = cosine_similarity(vec, self._ref_matrix)[0]

        best_idx = sims.argmax()
        best_score = float(sims[best_idx])
        best_stage, best_phrase = self._stage_of_ref[best_idx]

        # aggregate best score per stage, for transparency / debugging
        per_stage_best = {s: 0.0 for s in STAGES}
        for i, (stage, _phrase) in enumerate(self._stage_of_ref):
            if float(sims[i]) > per_stage_best[stage]:
                per_stage_best[stage] = float(sims[i])

        if best_score < self.THRESHOLD:
            return MatchResult(None, best_score, None, per_stage_best)

        return MatchResult(best_stage, best_score, best_phrase, per_stage_best)


class LaBSEMatcher:
    """
    Optional cross-lingual semantic matcher. Requires:
        pip install sentence-transformers torch
    and an internet connection on first run to download the model.

    Not used by default / not exercised by the test harness in this sandbox
    (no internet access here) -- provided so the real deployment described
    in the architecture slide is a couple of lines away, not a rewrite.
    """

    MODEL_NAME = "sentence-transformers/LaBSE"
    THRESHOLD = 0.60  # cosine similarity on true sentence embeddings runs higher

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError as e:
            raise ImportError(
                "LaBSEMatcher requires `pip install sentence-transformers torch`."
            ) from e

        self._util = util
        self._model = SentenceTransformer(self.MODEL_NAME)

        self._stage_of_ref = []
        corpus = []
        for stage in STAGES:
            for _lang, phrase in REFERENCE_PHRASES[stage]:
                corpus.append(phrase)
                self._stage_of_ref.append((stage, phrase))

        self._ref_embeddings = self._model.encode(corpus, convert_to_tensor=True)

    def classify(self, chunk_text: str) -> MatchResult:
        if not chunk_text or not chunk_text.strip():
            return MatchResult(None, 0.0, None, {})

        chunk_emb = self._model.encode([chunk_text], convert_to_tensor=True)
        sims = self._util.cos_sim(chunk_emb, self._ref_embeddings)[0].cpu().numpy()

        best_idx = sims.argmax()
        best_score = float(sims[best_idx])
        best_stage, best_phrase = self._stage_of_ref[best_idx]

        per_stage_best = {s: 0.0 for s in STAGES}
        for i, (stage, _phrase) in enumerate(self._stage_of_ref):
            if float(sims[i]) > per_stage_best[stage]:
                per_stage_best[stage] = float(sims[i])

        if best_score < self.THRESHOLD:
            return MatchResult(None, best_score, None, per_stage_best)

        return MatchResult(best_stage, best_score, best_phrase, per_stage_best)


def get_matcher(backend: str = "lite"):
    if backend == "lite":
        return LiteMatcher()
    if backend == "labse":
        return LaBSEMatcher()
    raise ValueError(f"Unknown backend: {backend!r} (expected 'lite' or 'labse')")
