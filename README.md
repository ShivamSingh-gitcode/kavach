# KAVACH — Conversational Fraud Defense

> **A scammer can change their phone number. They cannot easily hide the manipulation pattern.**

Kavach is an explainable prototype for detecting the conversational escalation pattern used in digital-arrest and related fraud calls:

```text
AUTHORITY CLAIM
      ↓
ISOLATION
      ↓
THREAT / URGENCY
      ↓
FINANCIAL DEMAND
      ↓
RISK ESCALATION / ALERT
```

The important distinction is that Kavach does not make the phone number the main decision. It evaluates what is happening **inside the conversation**.

## 1. What is Kavach?

The current repository combines:

- real local WAV playback in the browser;
- a local Faster-Whisper option for timestamped transcription;
- a checked-in timestamped transcript for a deterministic audio demo;
- the existing semantic stage matcher;
- the existing deterministic, sequence-aware risk engine;
- Server-Sent Events (SSE) for backend detection events;
- an explainable security-console UI.

**Honest prototype boundary:** the demo processes provided/recorded audio. It does **not** intercept cellular baseband audio, directly intercept encrypted WhatsApp calls, or bypass Android/iOS restrictions.

## 2. Problem

Digital-arrest scams commonly escalate through a social-engineering sequence. A caller may first establish false authority, isolate the victim, introduce legal pressure, and only then demand money or sensitive information.

A simple spam list can miss a conversation whose phone number is new, spoofed, or previously unknown.

### Traditional spam detection

```text
PHONE NUMBER
     ↓
KNOWN / UNKNOWN
     ↓
BLOCK / ALLOW
```

### Kavach

```text
CONVERSATION
     ↓
AUTHORITY
     ↓
ISOLATION
     ↓
THREAT / URGENCY
     ↓
FINANCIAL DEMAND
     ↓
RISK
```

## 3. Architecture

```text
CURRENT CONTROLLED AUDIO DEMO

WAV
 ↓
HTML5 Audio ───────────────→ Web Audio Analyser → real waveform
 ↓
timestamped transcript source
 ├─ MODE A: local Faster-Whisper
 └─ MODE B: checked-in transcript
 ↓
KavachPipeline.process_chunk()
 ↓
existing semantic matcher
 ↓
existing RiskEngine
 ↓
SSE
 ↓
browser transcript + stage + score + alert
```

The **WAV playback clock is the master clock** for Modes A and B. The server sends timestamped detection events; the browser reveals each event when `audio.currentTime` reaches that segment's start. The frontend never calculates the risk score.

### Detection engine boundary

These files are preserved as the core detection engine:

- `backend/pipeline.py`
- `backend/risk_engine.py`
- `backend/embeddings.py`
- `backend/reference_phrases.py`

The speech layer in `backend/stt.py` supplies transcript text and timestamps. Whisper does **not** decide whether a call is fraudulent.

## 4. Detection stages and risk scoring

The current engine assigns a stage the first time it fires:

| Stage | Base contribution |
|---|---:|
| Authority Claim | +20 |
| Isolation | +25 |
| Threat / Urgency | +25 |
| Financial Demand | +30 |
| Complete classic order bonus | +10 |

Tiers are:

| Score | Tier |
|---:|---|
| 0–24 | LOW |
| 25–49 | MEDIUM |
| 50–79 | HIGH |
| 80–110 | CRITICAL |

For the standard CBI sequence, the repository therefore produces **20 → 45 → 70 → 110**. The score values above are the actual preserved implementation; they should not be replaced with a different progression just for presentation.

The risk engine is sequence-aware but **sequence is not required**: a threat or financial demand can still contribute risk if earlier stages were skipped. The classic order receives an additional bonus.

## 5. Three demo scenarios

### A — Digital Arrest — CBI

Expected:

```text
Authority → Isolation → Threat/Urgency → Financial Demand
20 → 45 → 70 → 110
LOW → MEDIUM → HIGH → CRITICAL
```

The CRITICAL alert is emitted by the backend when `FINANCIAL_DEMAND` fires.

### B — Normal Conversation

A normal bank-card dispatch conversation. Expected final tier: **LOW**.

### C — Suspicious / Partial Scam

Expected:

```text
Authority → Isolation → Threat/Urgency
20 → 45 → 70
HIGH
```

There is no financial demand, so the scenario does not reach CRITICAL.

This third scenario is useful because it demonstrates that the concept is not simply `keyword detected = scam`.

## 6. Audio and STT modes

| Mode | Audio | Transcript | Detection | Recommended use |
|---|---|---|---|---|
| **A — Local Faster-Whisper** | Real WAV | Whisper timestamps | Real pipeline | Technical demonstration |
| **B — Audio + Precomputed** | Real WAV | Checked-in timestamps | Real pipeline | **Most reliable judge demo** |
| **C — Demo Fallback** | None required | Script + timing | Real pipeline | Last-resort offline path |

`AUTO` prefers Mode A when Faster-Whisper is installed and the WAV exists, then Mode B, then Mode C.

### Important distinction

Mode A is **local transcription of a prerecorded WAV before playback**. It is not live cellular-call STT.

The repository does not currently claim a live microphone, cellular, or WhatsApp ingestion adapter. The same `KavachPipeline.process_chunk(text)` interface is intentionally suitable for a future live adapter.

## 7. Windows installation

Open PowerShell in the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Create local configuration:

```powershell
Copy-Item .env.example .env
```

The application loads `.env` with `python-dotenv`.

### Default Whisper configuration

```text
KAVACH_WHISPER_MODEL=tiny
KAVACH_WHISPER_DEVICE=cpu
```

That means **tiny + CPU + int8** by default.

To let Faster-Whisper try CUDA first:

```powershell
$env:KAVACH_WHISPER_DEVICE="auto"
```

The first Whisper run may download model weights. After the model is available, inference is local.

## 8. Put the demo WAVs in place

The final repository contains three generated **synthetic local demo voices** so the judge demo is audible without a cloud service:

```text
frontend/assets/audio/script_01_cbi_classic.wav
frontend/assets/audio/control_01_bank_card_dispatch.wav
frontend/assets/audio/scenario_partial_suspicious.wav
```

They are 16-bit PCM mono WAVs with durations aligned to the checked-in transcript timings.

These are **synthetic narration for the prototype**, not authentic victim recordings.

If you replace them with your own recording, keep the same filenames and update the matching timing/transcript metadata when the pacing changes.

## 9. Run Kavach

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\server.py
```

Open:

```text
http://localhost:5000
```

Keep the backend terminal open.

## 10. Test the controlled audio demo

For the most reliable judging path:

```powershell
$env:KAVACH_DEMO_MODE="precomputed"
python backend\server.py
```

Then:

1. Select **Digital Arrest — CBI**.
2. Click **START DEMO CALL**.
3. Confirm the browser reports **MODE B — AUDIO + PRECOMPUTED TRANSCRIPT**.
4. You should hear the local WAV.
5. Watch the waveform react to the actual audio signal.
6. Watch transcript entries appear at their timestamp.
7. Watch the four stages fire in order.
8. Watch the backend score reach 70 at Threat/Urgency.
9. When the financial-demand sentence starts, watch the score reach 110 and the CRITICAL warning appear.
10. Run **Normal Conversation** and verify LOW.
11. Run **Suspicious / Partial Scam** and verify HIGH without CRITICAL.

The browser's `audio.currentTime` controls when the transcript/detection event becomes visible in Modes A/B.

## 11. Test local Faster-Whisper

Use a separate terminal or stop/restart the server:

```powershell
$env:KAVACH_DEMO_MODE="whisper"
$env:KAVACH_WHISPER_MODEL="tiny"
$env:KAVACH_WHISPER_DEVICE="cpu"
python backend\server.py
```

Select the CBI scenario and start the demo.

The preparation step:

```text
WAV
 ↓
Faster-Whisper
 ↓
timestamped transcript segments
 ↓
KavachPipeline
 ↓
RiskEngine
 ↓
SSE
```

If Whisper fails to load or returns no usable segments, the server can fall back to Mode B when the precomputed transcript exists. The UI explicitly identifies the selected mode and reports the fallback.

### Verify the Whisper dependency directly

```powershell
python -c "from faster_whisper import WhisperModel; print('Faster-Whisper import OK')"
```

### Test the actual WAV with Whisper

A simple smoke test:

```powershell
python -c "from backend.stt import WhisperTranscriber; print(WhisperTranscriber().transcribe('frontend/assets/audio/script_01_cbi_classic.wav'))"
```

This is **prerecorded local STT**, not live call interception.

## 12. Existing evaluation

Run:

```powershell
python tests
un_evaluation.py
```

Verbose:

```powershell
python tests
un_evaluation.py --verbose
```

Markdown:

```powershell
python tests
un_evaluation.py --markdown
```

The evaluation harness uses the offline deterministic `lite` matcher and does not require Whisper.

Current repository result:

- **5/5** scam scripts reached HIGH or CRITICAL.
- **3/5** reached HIGH/CRITICAL before the financial-demand line.
- **3/4** benign controls remained LOW.
- **1/4** benign controls reached HIGH because an OTP phrase was ambiguous to the offline matcher.

This is a **small internal prototype evaluation, not production accuracy**.

## 13. Limitations

### Current prototype

- Processes provided audio streams / recorded calls.
- Does not intercept cellular baseband audio.
- Does not directly intercept encrypted WhatsApp calls.
- Does not bypass Android/iOS platform restrictions.
- Faster-Whisper CPU performance depends on hardware.
- The benchmark is small and self-written.
- The offline `lite` matcher is a deterministic character n-gram TF-IDF matcher, not a production-scale multilingual semantic model.
- The project does not imply telecom, banking, police, government, or platform partnerships.

### Future production deployment

Potential next steps, subject to platform, legal and privacy constraints:

- permitted telecom/OS-level audio integration;
- true streaming speech recognition;
- multilingual and code-switching models;
- larger, independently designed evaluation datasets;
- privacy-preserving edge inference;
- calibrated confidence and false-positive controls;
- integration with existing fraud-reporting and response ecosystems.

These are **future deployment directions, not current capabilities**.

## 14. Judge-facing claims

### Safe claims

You can say:

- “Kavach detects a conversational escalation pattern rather than relying only on a phone number.”
- “The risk decision comes from a deterministic backend pipeline and is explainable by stage.”
- “The demo uses real local WAV playback and a waveform derived from the actual audio signal.”
- “Faster-Whisper can transcribe the prerecorded WAV locally.”
- “The CBI demo reaches CRITICAL when the financial-demand stage fires.”
- “The partial scenario reaches HIGH without a financial demand.”
- “Our internal prototype benchmark is reproducible and intentionally small.”

### Do not claim

Do **not** say:

- “Kavach intercepts every phone or WhatsApp call.”
- “Kavach bypasses Android restrictions.”
- “Kavach is 100% accurate.”
- “5/5 means 100% real-world accuracy.”
- “The system is trained on real victim calls” — it is not.
- “Whisper is live cellular interception” — it is not.
- “The frontend timer is the AI” — the audio clock controls the demo display, while risk comes from the backend.
- “We have government/telecom/police integration” unless such a partnership actually exists.

## 15. Repository map

```text
kavach/
├── backend/
│   ├── server.py
│   ├── stt.py
│   ├── pipeline.py
│   ├── risk_engine.py
│   ├── embeddings.py
│   └── reference_phrases.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── assets/audio/*.wav
├── data/test_scripts/
├── tests/run_evaluation.py
├── tools/create_demo_audio.ps1
└── docs/
    ├── architecture.md
    ├── evaluation_results.md
    └── judge_demo.md
```

## 16. Team information

Add the actual team information before submission:

```text
Team Name:
Team Members:
College / Institution:
Problem Statement:
Team ID:
Repository:
```

## License

MIT — see `LICENSE`.


### Current CBI controlled-demo audio

The bundled CBI WAV is a ~30.16 second synthetic demo conversation with five timestamped segments:
1. CBI authority claim
2. victim baseline response
3. isolation instruction
4. arrest threat / urgency
5. fifty-thousand-rupee financial demand

The controlled transcript includes speaker labels and is synchronized to the bundled WAV. In presentation mode, `audio.currentTime` is the playback clock. The CBI sequence reaches the preserved engine's actual score progression **20 → 45 → 70 → 110**; CRITICAL appears only when the financial-demand segment is processed.

## Hindi CBI demo recording

The bundled CBI Digital Arrest demo uses the user-provided Hindi/Hinglish recording `frontend/assets/audio/script_01_cbi_classic.wav` (converted to 16 kHz mono WAV for browser playback). Its transcript and timing metadata are stored in `data/test_scripts/script_01_cbi_classic.transcript.json` and `data/test_scripts/script_01_cbi_classic.timing.json`. The detection engine files are unchanged.
