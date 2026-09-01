# Creates three local demo WAVs with Windows' built-in SpeechSynthesizer.
# This is a convenient way to get audible files without a cloud API.
# Voice availability depends on the Windows language packs installed.
#
# Run from the kavach project root:
#   powershell -ExecutionPolicy Bypass -File .\tools\create_demo_audio.ps1
#
# These are synthetic demo voices, not authentic call recordings.
# For the strongest presentation, replace them with your own recorded
# narration or a locally-run TTS voice.

Add-Type -AssemblyName System.Speech

$outDir = Join-Path $PSScriptRoot "..\frontend\assets\audio"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Write-Wav($filename, $lines) {
    $path = Join-Path $outDir $filename
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.Rate = 0
    $synth.Volume = 100
    $synth.SetOutputToWaveFile($path)
    foreach ($line in $lines) {
        $synth.Speak($line)
        $synth.Speak(" ")
    }
    $synth.SetOutputToNull()
    $synth.Dispose()
    Write-Host "Created $path"
}

Write-Wav "script_01_cbi_classic.wav" @(
    "Hello. I am calling from the CBI regarding a serious money laundering case against you. This is Senior Officer Sharma.",
    "Sir, what case? I do not know anything about this.",
    "Do not disconnect this call. You must not tell any family member about this investigation. Move to a private room now.",
    "If you do not cooperate, an immediate arrest warrant will be issued and the police will be sent to your address.",
    "To clear the case, you must transfer fifty thousand rupees as a temporary security deposit. Please transfer the money now."
)
Write-Wav "control_01_bank_card_dispatch.wav" @(
    "Hi, this is your bank calling to confirm your new debit card has been dispatched.",
    "It should reach your registered address within five to seven working days.",
    "Please let us know if you do not receive it by next week.",
    "You can also track the delivery status using the reference number sent to your email."
)

Write-Wav "scenario_partial_suspicious.wav" @(
    "This is the cyber crime cell, we need to verify your identity regarding a pending matter.",
    "This is a confidential matter, please do not discuss it with anyone at this time.",
    "You have very little time to respond before legal action is taken.",
    "We will note your cooperation and follow up with further instructions later."
)

Write-Host ""
Write-Host "Done. These are synthetic local demo voices. For Mode B, update the timing JSON if their pacing differs."
