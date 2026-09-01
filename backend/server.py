"""
server.py — Kavach demo backend.

The detection engine is unchanged. This server only chooses the transcript
source and feeds transcript segments into the existing KavachPipeline.

Demo modes:
A. whisper       actual WAV -> local Faster-Whisper timestamps -> pipeline -> SSE
B. precomputed   actual WAV -> local timestamped transcript -> pipeline -> SSE
C. fallback      no usable audio/STT -> existing script + timing replay -> pipeline

Risk/stage/tier/alert always come from KavachPipeline/RiskEngine. The browser
never invents a score or stage.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from threading import Lock

from flask import Flask, Response, jsonify, request, send_from_directory
from dotenv import load_dotenv

from pipeline import KavachPipeline
from stt import WhisperTranscriber, TranscriptSegment, load_precomputed


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data" / "test_scripts"
AUDIO_DIR = FRONTEND_DIR / "assets" / "audio"

FALLBACK_CHUNK_DELAY_SECONDS = 1.5

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

DEMO_SCENARIOS = {
    "cbi_digital_arrest": {
        "label": "Digital Arrest — CBI",
        "description": "Full escalation: Authority -> Isolation -> Threat/Urgency -> Financial Demand.",
        "script_file": "script_01_cbi_classic.txt",
        "timing_file": "script_01_cbi_classic.timing.json",
        "transcript_file": "script_01_cbi_classic.transcript.json",
        "audio_file": "script_01_cbi_classic.wav",
        "expected_outcome": "CRITICAL",
        "caller_id": "+91 98XXXXXX12",
        "caller_status": "Unknown caller",
    },
    "normal_conversation": {
        "label": "Normal Conversation",
        "description": "Ordinary bank customer-service call. Should stay LOW throughout.",
        "script_file": "control_01_bank_card_dispatch.txt",
        "timing_file": "control_01_bank_card_dispatch.timing.json",
        "transcript_file": "control_01_bank_card_dispatch.transcript.json",
        "audio_file": "control_01_bank_card_dispatch.wav",
        "expected_outcome": "LOW",
        "caller_id": "HDFC Bank Care",
        "caller_status": "Saved contact",
    },
    "partial_suspicious": {
        "label": "Suspicious / Partial Scam",
        "description": "Authority, Isolation and Threat/Urgency fire; no financial demand. Should plateau at HIGH.",
        "script_file": "scenario_partial_suspicious.txt",
        "timing_file": "scenario_partial_suspicious.timing.json",
        "transcript_file": "scenario_partial_suspicious.transcript.json",
        "audio_file": "scenario_partial_suspicious.wav",
        "expected_outcome": "HIGH",
        "caller_id": "+91 90XXXXXX47",
        "caller_status": "Unknown caller",
    },
}

_whisper = WhisperTranscriber()
_transcript_cache = {}
_cache_lock = Lock()


def _load_script(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_timing(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _audio_path(cfg):
    return AUDIO_DIR / cfg["audio_file"]


def _audio_available(cfg):
    return _audio_path(cfg).exists()


def _script_segments(cfg):
    lines = _load_script(cfg["script_file"]) or []
    timing = _load_timing(cfg["timing_file"]) or {}
    timing_lines = timing.get("lines", [])
    result = []
    for i, text in enumerate(lines):
        item = timing_lines[i] if i < len(timing_lines) else {}
        start = float(item.get("start", i * FALLBACK_CHUNK_DELAY_SECONDS))
        end = float(item.get("end", start + FALLBACK_CHUNK_DELAY_SECONDS))
        result.append(TranscriptSegment(i + 1, start, max(start, end), text, "CALLER"))
    return result


def _precomputed_path(cfg):
    return DATA_DIR / cfg["transcript_file"]


def _resolve_mode(cfg, requested=None):
    requested = (requested or os.getenv("KAVACH_DEMO_MODE", "auto")).lower()
    if requested not in {"auto", "whisper", "precomputed", "fallback"}:
        requested = "auto"

    has_audio = _audio_available(cfg)
    if requested == "fallback":
        return "fallback"
    if requested == "precomputed":
        return "precomputed" if has_audio else "fallback"
    if requested == "whisper":
        return "whisper" if has_audio else "fallback"

    # AUTO is presentation-safe by default: use the checked-in transcript
    # when a WAV is available so the spoken audio, transcript and risk stages
    # remain deterministic. Whisper remains explicitly selectable.
    if has_audio and _precomputed_path(cfg).exists():
        return "precomputed"
    if has_audio and os.getenv("KAVACH_DISABLE_WHISPER", "0").lower() not in {"1", "true", "yes"}:
        try:
            import faster_whisper  # noqa: F401
            return "whisper"
        except ImportError:
            pass
    return "fallback"


def _get_segments(scenario_id, mode):
    cfg = DEMO_SCENARIOS[scenario_id]
    key = (scenario_id, mode)
    with _cache_lock:
        if key in _transcript_cache:
            return _transcript_cache[key]

    if mode == "whisper":
        segments = _whisper.transcribe(str(_audio_path(cfg)))
    elif mode == "precomputed":
        segments = load_precomputed(str(_precomputed_path(cfg)))
    else:
        segments = _script_segments(cfg)

    with _cache_lock:
        _transcript_cache[key] = segments
    return segments


@app.route("/api/scenarios")
def list_scenarios():
    out = []
    for scenario_id, cfg in DEMO_SCENARIOS.items():
        timing = _load_timing(cfg["timing_file"]) or {}
        out.append({
            "id": scenario_id,
            "label": cfg["label"],
            "description": cfg["description"],
            "expected_outcome": cfg["expected_outcome"],
            "caller_id": cfg["caller_id"],
            "caller_status": cfg["caller_status"],
            "audio_url": f"/assets/audio/{cfg['audio_file']}",
            "audio_available": _audio_available(cfg),
            "fallback_duration": timing.get("total_duration"),
        })
    return jsonify({"scenarios": out})


@app.route("/api/demo/prepare/<scenario_id>")
def prepare_demo(scenario_id):
    cfg = DEMO_SCENARIOS.get(scenario_id)
    if cfg is None:
        return jsonify({"error": "unknown scenario"}), 404

    requested = request.args.get("mode")
    mode = _resolve_mode(cfg, requested)

    try:
        segments = _get_segments(scenario_id, mode)
        return jsonify({
            "scenario_id": scenario_id,
            "mode": mode,
            "mode_label": {
                "whisper": "MODE A — LOCAL WHISPER",
                "precomputed": "MODE B — AUDIO + PRECOMPUTED TRANSCRIPT",
                "fallback": "MODE C — DEMO FALLBACK",
            }[mode],
            "audio_available": _audio_available(cfg),
            "whisper": _whisper.status(),
            "segments": [s.as_dict() for s in segments],
        })
    except Exception as exc:
        # AUTO/WHISPER gracefully drops to precomputed if possible.
        if mode == "whisper":
            try:
                fallback_mode = "precomputed" if _audio_available(cfg) and _precomputed_path(cfg).exists() else "fallback"
                segments = _get_segments(scenario_id, fallback_mode)
                return jsonify({
                    "scenario_id": scenario_id,
                    "mode": fallback_mode,
                    "mode_label": "MODE B — AUDIO + PRECOMPUTED TRANSCRIPT" if fallback_mode == "precomputed" else "MODE C — DEMO FALLBACK",
                    "audio_available": _audio_available(cfg),
                    "whisper": _whisper.status(),
                    "warning": f"Local Whisper unavailable: {exc}",
                    "segments": [s.as_dict() for s in segments],
                })
            except Exception:
                pass
        return jsonify({"error": str(exc), "mode": mode}), 503


@app.route("/api/stream/<scenario_id>")
def stream(scenario_id):
    cfg = DEMO_SCENARIOS.get(scenario_id)
    if cfg is None:
        return jsonify({"error": "unknown scenario"}), 404

    requested_mode = request.args.get("mode")
    mode = _resolve_mode(cfg, requested_mode)
    try:
        segments = _get_segments(scenario_id, mode)
    except Exception as exc:
        return jsonify({"error": str(exc), "mode": mode}), 503

    # Resume support: the browser can reconnect after a pause. We replay
    # already-heard chunks into a fresh engine silently, then continue at the
    # requested audio position. This keeps the risk state server-side.
    try:
        from_index = max(0, int(request.args.get("from", "0")))
    except ValueError:
        from_index = 0
    try:
        audio_position = max(0.0, float(request.args.get("at", "0")))
    except ValueError:
        audio_position = 0.0

    def generate():
        pipeline = KavachPipeline(backend="lite")
        for seg in segments[:from_index]:
            pipeline.process_chunk(seg.text)

        started_at = time.monotonic()
        audio_clocked = mode in {"whisper", "precomputed"}

        for i, seg in enumerate(segments[from_index:], start=from_index):
            # In audio modes the browser's HTML5 audio element is the master
            # clock. The server therefore sends timestamped detection events
            # without inventing a second wall-clock timer; the browser reveals
            # each event when audio.currentTime reaches seg.start.
            if not audio_clocked:
                target_offset = max(0.0, seg.start - audio_position)
                elapsed = time.monotonic() - started_at
                sleep_for = target_offset - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

            event = pipeline.process_chunk(seg.text)
            payload = {
                "mode": mode,
                "chunk_index": event.chunk_index,
                "line_index": i,
                "text": event.text,
                "speaker": getattr(seg, "speaker", "CALLER"),
                "start": seg.start,
                "end": seg.end,
                "matched_stage": event.matched_stage,
                "confidence": event.confidence,
                "matched_reference": event.matched_reference,
                "new_stage_fired": event.new_stage_fired,
                "score": event.score,
                "tier": event.tier,
                "fired_stages": event.fired_stages,
                "max_possible": pipeline.summary()["max_possible"],
                "elapsed": round(time.monotonic() - started_at + audio_position, 2),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        summary = pipeline.summary()
        yield f"event: done\ndata: {json.dumps(summary)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@app.route("/assets/audio/<path:filename>")
def audio_asset(filename):
    full_path = AUDIO_DIR / filename
    if not full_path.exists():
        return jsonify({"error": "audio file not present", "filename": filename}), 404
    return send_from_directory(str(AUDIO_DIR), filename)


@app.route("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False, threaded=True)
