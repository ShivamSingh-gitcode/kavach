# Kavach — Runtime Architecture

Kavach preserves the existing detection engine and adds a speech/audio presentation layer around it.

## Current controlled audio flow

```text
REAL LOCAL WAV
      │
      ├──────────────→ HTML5 Audio
      │                    │
      │                    └→ Web Audio Analyser → waveform
      │
      └→ transcript source
             ├─ MODE A: local Faster-Whisper
             └─ MODE B: checked-in timestamped transcript
                         │
                         ↓
                KavachPipeline.process_chunk()
                         ↓
                  semantic matcher
                         ↓
                    RiskEngine
                         ↓
                       SSE
                         ↓
                 browser event queue
                         ↓
             reveal when audio.currentTime
             reaches segment start
```

## Why the audio clock matters

Modes A and B do not use a separate frontend countdown to pretend that detection is synchronized.

The browser receives timestamped backend events and compares their `start` timestamp with the actual `HTMLAudioElement.currentTime`. The WAV is therefore the master clock for what the judge sees.

The server does not manufacture a second clock for audio modes. It computes the detection event once, sends the event data through SSE, and lets the browser reveal it at the matching audio position.

## Mode A — local Faster-Whisper

```text
WAV
 ↓
Faster-Whisper (local)
 ↓
timestamped segments
 ↓
KavachPipeline.process_chunk(text)
 ↓
existing matcher
 ↓
existing RiskEngine
 ↓
SSE event
 ↓
browser
```

`backend/stt.py` only supplies text and timestamps. It does not assign fraud risk.

Default configuration:

```text
KAVACH_WHISPER_MODEL=tiny
KAVACH_WHISPER_DEVICE=cpu
```

`auto` is available when CUDA/FP16 is desired.

Mode A transcribes a **prerecorded WAV before playback**. It is not a live microphone, cellular, or WhatsApp interception system.

## Mode B — deterministic audio demo

```text
WAV ─────────────────────────→ browser audio + real waveform
 ↓
checked-in timestamped transcript
 ↓
KavachPipeline
 ↓
existing matcher + RiskEngine
 ↓
SSE
 ↓
browser
```

This is the recommended judging mode because it is deterministic while still demonstrating actual audio playback, actual waveform rendering, timestamped transcript progression, and the real backend detection engine.

## Mode C — existing fallback

```text
script + timing JSON
 ↓
KavachPipeline
 ↓
RiskEngine
 ↓
SSE
```

Mode C exists as the last-resort path if audio or STT is unavailable. The UI explicitly labels it `MODE C — DEMO FALLBACK`.

## Pause / resume

For audio modes:

1. Pause stops the WAV.
2. The SSE connection is closed.
3. Resume reconnects from the beginning.
4. The backend silently reconstructs risk state from all transcript segments.
5. The browser ignores events already displayed and reveals any remaining event according to the current audio position.

This keeps risk state server-side and avoids a second client-side risk implementation.

## AudioContext lifecycle

The browser creates exactly one `AudioContext` and one `MediaElementAudioSourceNode` for the lifetime of the page. Switching scenarios reuses that graph rather than creating another source connection.

If Web Audio analysis is unavailable, WAV playback still works; the UI reports that the analyser is unavailable rather than pretending the waveform is real.

## Backend source of truth

The frontend never decides:

- which stage fired;
- what score to assign;
- which tier to show;
- when the backend should raise CRITICAL.

Those values come from the existing pipeline/risk engine and are transported through SSE.

## Core files preserved

- `backend/pipeline.py`
- `backend/risk_engine.py`
- `backend/embeddings.py`
- `backend/reference_phrases.py`
- `tests/run_evaluation.py`

No detection algorithm was changed for the UI/audio work.
