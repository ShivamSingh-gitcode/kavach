"""
stt.py — optional local Faster-Whisper adapter for Kavach.

The adapter has one responsibility: turn a prerecorded WAV into timestamped
transcript segments. It never assigns a scam stage or a risk score. The
resulting text is always passed to KavachPipeline, exactly like a live text
chunk would be.

Modes:
- whisper: Faster-Whisper transcribes the actual WAV locally before playback.
- precomputed: timestamped transcript JSON is used; KavachPipeline still
  performs the real detection.
- fallback: the existing timing/script replay is used when audio/STT is not
  available.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class TranscriptSegment:
    index: int
    start: float
    end: float
    text: str
    speaker: str = "CALLER"

    def as_dict(self) -> dict:
        return asdict(self)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class WhisperTranscriber:
    """Lazy, configurable Faster-Whisper loader.

    The model is loaded only when Whisper mode is actually requested, so the
    normal lite evaluation harness never needs Whisper installed.
    """

    def __init__(self):
        self.model_name = os.getenv("KAVACH_WHISPER_MODEL", "tiny")
        self.model_path = os.getenv("KAVACH_WHISPER_MODEL_PATH", "").strip()
        self.device_preference = os.getenv("KAVACH_WHISPER_DEVICE", "cpu").lower()
        self.cpu_threads = int(os.getenv("KAVACH_WHISPER_CPU_THREADS", "4"))
        self.model = None
        self.loaded_device = None
        self.loaded_compute_type = None

    def _load(self):
        if self.model is not None:
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Faster-Whisper is not installed. Run `pip install faster-whisper` "
                "or use DEMO_MODE=precomputed/auto."
            ) from exc

        model_id = self.model_path or self.model_name
        attempts = []

        if self.device_preference in ("auto", "cuda", "gpu"):
            attempts.append(("cuda", "float16"))
        attempts.append(("cpu", "int8"))

        last_error = None
        for device, compute_type in attempts:
            try:
                kwargs = {
                    "device": device,
                    "compute_type": compute_type,
                    "cpu_threads": self.cpu_threads,
                }
                self.model = WhisperModel(model_id, **kwargs)
                self.loaded_device = device
                self.loaded_compute_type = compute_type
                return
            except Exception as exc:  # CUDA/model availability varies by machine.
                last_error = exc
                self.model = None

        raise RuntimeError(
            f"Could not load Faster-Whisper model {model_id!r}. "
            f"Last error: {last_error}"
        )

    def transcribe(self, audio_path: str) -> List[TranscriptSegment]:
        self._load()

        language = os.getenv("KAVACH_WHISPER_LANGUAGE", "").strip() or None
        beam_size = int(os.getenv("KAVACH_WHISPER_BEAM_SIZE", "1"))
        vad_filter = _env_bool("KAVACH_WHISPER_VAD_FILTER", True)

        segments, _info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
            condition_on_previous_text=True,
            word_timestamps=False,
        )

        result: List[TranscriptSegment] = []
        for i, segment in enumerate(segments):
            text = (segment.text or "").strip()
            if not text:
                continue
            result.append(
                TranscriptSegment(
                    index=i + 1,
                    start=max(0.0, float(segment.start)),
                    end=max(float(segment.start), float(segment.end)),
                    text=text,
                    speaker="CALLER",
                )
            )

        if not result:
            raise RuntimeError("Faster-Whisper returned no non-empty transcript segments.")
        return result

    def status(self) -> dict:
        return {
            "installed": self.model is not None,
            "model": self.model_path or self.model_name,
            "device": self.loaded_device,
            "compute_type": self.loaded_compute_type,
        }


def load_precomputed(path: str) -> List[TranscriptSegment]:
    """Load a small timestamped transcript JSON generated for demo replay."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    for i, item in enumerate(data.get("segments", [])):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        start = float(item["start"])
        end = float(item["end"])
        segments.append(TranscriptSegment(i + 1, start, max(start, end), text, str(item.get("speaker", "CALLER"))))

    if not segments:
        raise RuntimeError(f"No transcript segments found in {path}")
    return segments


def write_precomputed(path: str, segments: List[TranscriptSegment], source: str):
    payload = {
        "format": "kavach-precomputed-transcript-v1",
        "source": source,
        "segments": [s.as_dict() for s in segments],
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
