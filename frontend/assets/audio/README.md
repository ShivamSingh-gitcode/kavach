# Kavach demo WAVs

The repository includes three synthetic local narration WAVs for the hackathon demo:

| Filename | Scenario | Duration |
|---|---|---:|
| `script_01_cbi_classic.wav` | CBI Digital Arrest | 28.5 s |
| `control_01_bank_card_dispatch.wav` | Normal Conversation | 16.5 s |
| `scenario_partial_suspicious.wav` | Suspicious / Partial | 19.5 s |

They are **synthetic demo voices**, not authentic call recordings.

Recommended format:

- WAV container
- PCM 16-bit
- mono
- 16 kHz
- spoken content in the same order as the matching transcript

## Synchronization

For MODE A, Faster-Whisper creates timestamps from the actual WAV.

For MODE B, the checked-in `data/test_scripts/*.transcript.json` files provide deterministic timestamps. The browser uses `audio.currentTime` as the master clock and reveals each backend event when its timestamp is reached.

The transcript is never used to fabricate a frontend risk score: every displayed stage/score/tier is returned by the backend `KavachPipeline` + `RiskEngine`.

If you replace a WAV with substantially different pacing, update the corresponding transcript/timing metadata or use MODE A so timestamps are derived from the new audio.

## Regenerating synthetic audio on Windows

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\create_demo_audio.ps1
```

The script uses Windows `System.Speech` and creates local WAVs. Voice availability depends on installed Windows language packs, so regenerated durations may differ from the checked-in files; re-check the timing metadata if you regenerate them.

For the final judge demo, the checked-in WAVs are the known-good deterministic audio assets.
