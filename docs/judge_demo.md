# Kavach — 2–3 Minute Judge Demo

## Before the demo

Recommended setup:

```powershell
$env:KAVACH_DEMO_MODE="precomputed"
python backend\server.py
```

Open `http://localhost:5000`.

Use **MODE B — audio + precomputed transcript** for the most reliable judging run. It uses the real local WAV and the real backend detection engine without depending on CPU Whisper preparation during the presentation.

---

## 0:00 — Set the problem

**Say:**

> “Most spam systems ask one question: is this number suspicious? Kavach asks a different question: what is the caller trying to make the victim do?”

Point to the top **THE DIFFERENCE** strip:

```text
Traditional: number → block / allow
Kavach: conversation → escalation pattern → risk
```

---

## 0:15 — Start the CBI scenario

Select:

**Digital Arrest — CBI**

Click:

**START DEMO CALL**

**Say:**

> “This is a controlled prerecorded call. The audio is real local WAV playback, and the waveform you see is derived from that actual audio signal. The detection decision is made in the backend.”

Point out the mode badge:

**MODE B — AUDIO + PRECOMPUTED TRANSCRIPT**

If demonstrating Mode A instead, say:

> “Here the same WAV is transcribed locally with Faster-Whisper before playback. Whisper provides timestamps and text; it does not decide the risk.”

---

## 0:30 — AUTHORITY (about 0:00–0:06.4 in the call)

When the first transcript line appears and **AUTHORITY CLAIM** lights up:

**Say:**

> “First, the caller establishes false authority — claiming to be a CBI officer.”

Point to:

- transcript line;
- `AUTHORITY CLAIM`;
- first stage indicator;
- risk score.

Do not say the frontend detected the phrase. Say the backend stage matcher fired.

---

## 0:50 — ISOLATION (about 0:10.3–0:16.8 in the call)

When **ISOLATION** fires:

**Say:**

> “Next, the caller tries to isolate the victim — telling them not to disconnect or tell family members.”

Point to the second stage.

**Key idea:**

> “Kavach is tracking escalation, not just one suspicious word.”

---

## 1:10 — THREAT / URGENCY (about 0:17.4–0:22.7 in the call)

When **THREAT / URGENCY** fires:

**Say:**

> “Now the pressure escalates into arrest threats and a short deadline.”

Point to:

- third stage;
- HIGH tier;
- risk score of **70** in the current preserved engine.

Pause for a moment so the judge can see the sequence.

---

## 1:30 — FINANCIAL DEMAND → CRITICAL (about 0:23.2–0:30.2 in the call)

When the financial-demand sentence starts:

**Say:**

> “Only now does the explicit financial demand appear.”

When the CRITICAL alert appears:

> “The backend has now identified the complete manipulation sequence and escalated the call to CRITICAL.”

Point to the alert and say:

> “The recommended user response is simple: do not transfer money, do not share OTP or PIN, and contact someone you trust.”

Do not call this an AI-generated warning. It is the result of the deterministic risk engine.

---

## 1:55 — Normal Conversation

Switch to:

**Normal Conversation**

Start the call.

**Say:**

> “Now let’s test the opposite case.”

Let it run briefly.

> “This ordinary bank-card dispatch conversation stays LOW because the scam escalation sequence is not present.”

Point to the LOW tier and the empty stage progression.

---

## 2:15 — Suspicious / Partial

Switch to:

**Suspicious / Partial Scam**

Start the call.

When the third stage fires:

> “This one is intentionally incomplete. Authority, isolation and threat are present, so the risk reaches HIGH…”

Then:

> “…but there is no financial demand, so it does not reach CRITICAL.”

Point to the stage list: the fourth stage remains unfired.

---

## 2:35 — Close

**Say:**

> “That is the core idea behind Kavach: the phone number can change, but the manipulation pattern is much harder for a scammer to hide.”

Then add the boundary:

> “This prototype processes recorded or provided audio. It does not intercept cellular or encrypted WhatsApp calls. The next deployment step would require permitted OS or telecom integration, larger evaluation data, multilingual models and privacy-preserving edge inference.”

---


## CBI call transcript used by the bundled audio

The controlled CBI WAV and precomputed transcript use these exact five segments:

**CALLER — AUTHORITY**
> “Hello. I am calling from the CBI regarding a serious money laundering case against you. This is Senior Officer Sharma.”

**VICTIM — BASELINE**
> “Sir, what case? I do not know anything about this.”

**CALLER — ISOLATION**
> “Do not disconnect this call. You must not tell any family member about this investigation. Move to a private room now.”

**CALLER — THREAT / URGENCY**
> “If you do not cooperate, an immediate arrest warrant will be issued and the police will be sent to your address.”

**CALLER — FINANCIAL DEMAND**
> “To clear the case, you must transfer fifty thousand rupees as a temporary security deposit. Please transfer the money now.”

The bundled WAV is approximately **30.16 seconds**. The victim line is intentionally short and does not trigger a scam stage; the next caller line triggers isolation. This makes the behavioral progression easy to see during judging.

# What the judge should see

### CBI

```text
AUTHORITY
   ↓
ISOLATION
   ↓
THREAT / URGENCY
   ↓
FINANCIAL DEMAND
   ↓
CRITICAL
```

### Normal

```text
No meaningful scam sequence
        ↓
LOW
```

### Partial

```text
AUTHORITY
   ↓
ISOLATION
   ↓
THREAT / URGENCY
   ↓
HIGH
(no financial demand)
```

# If Whisper is slow

Do not wait during the final presentation.

Use:

```powershell
$env:KAVACH_DEMO_MODE="precomputed"
python backend\server.py
```

This is not a fake simulation: the browser still plays the real WAV, the waveform comes from that WAV, every transcript segment goes through the real Kavach pipeline, and the risk/stage values come from the backend.

# If audio playback is blocked

The first click is already a user gesture in normal browser operation. If the browser still blocks playback, click **PLAY / RESUME** in the audio panel.

Do not switch to a fake timer. The controlled audio demo should remain tied to `audio.currentTime`.

## Hindi CBI demo recording

The bundled CBI Digital Arrest demo uses the user-provided Hindi/Hinglish recording `frontend/assets/audio/script_01_cbi_classic.wav` (converted to 16 kHz mono WAV for browser playback). Its transcript and timing metadata are stored in `data/test_scripts/script_01_cbi_classic.transcript.json` and `data/test_scripts/script_01_cbi_classic.timing.json`. The detection engine files are unchanged.
