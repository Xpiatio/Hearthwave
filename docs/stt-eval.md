# STT Evaluation Workflow

How to measure transcription accuracy on real radio audio so DSP/model
changes are judged by word-error-rate (WER), not by gut feel.

## 1. Collect captures from live audio

1. In the Radio-TTY config UI (or `data/config.json`), set
   `"stt_debug_capture": true`. Restart listening (toggling Listen or
   changing the setting over WebSocket restarts the worker).
2. Feed the system real radio audio. Two options:
   - **Off the air:** normal RX through your radio's audio cable.
   - **System loopback:** select the *System Audio Loopback* input and play
     recordings of GMRS/FRS/scanner traffic (e.g. YouTube) on the same
     machine. Good for repeatable A/B corpora.
3. Each detected utterance is written to `/data/debug/stt/utt_<ts>_<id>/`:
   - `raw.wav` — pre-DSP audio including pre-roll context (label this one)
   - `segmented.wav` — what the segmenter handed to transcription
   - `processed.wav` — what Whisper actually saw (post bandpass/denoise/AGC)
   - `transcript.json` — live partial/final texts + config snapshot

## 2. Label references

Listen to `raw.wav` and write what was actually said into a
`reference.txt` file in the same utterance directory:

```
echo "kdq one two three radio check over" > /data/debug/stt/utt_.../reference.txt
```

Plain lowercase text; punctuation is ignored by the scorer. Standalone WAVs
(outside capture dirs) can be labelled with a sibling `<stem>.txt` instead.

## 3. Score

From the repo root:

```
python -m backend.tools.eval_stt --audio /data/debug/stt
```

Useful experiments:

```
--no-denoise              # is noisereduce helping or hurting on FM static?
--gain-mode {agc,rms,off} # gain stage after bandpass/denoise (default: agc)
--no-lowpass              # isolate individual DSP stages
--model medium.en         # bigger model on identical audio
--vad-threshold 0.35      # earlier VAD onset in noise
--squelch-threshold 0.03  # weaker-carrier pre-trigger
--min-speech-s 0.25       # do short replies ("copy") survive?
--beam-size 8             # wider beam search (faster-whisper default: 5)
--repetition-penalty 1.2  # penalize repeated tokens
--no-repeat-ngram-size 3  # block repeated n-grams of this size
--hotwords "kdq alpha"    # bias decoding toward specific words/callsigns
--word-confidence-min 0.4 # drop words below this per-word confidence
--prompt-style transcript # initial_prompt rendering: list (default) or transcript
--vad-min-silence-ms 800  # Silero VAD min_silence_duration_ms (default: 500)
--vad-speech-pad-ms 300   # Silero VAD speech_pad_ms (default: 200)
--noise-profile auto      # stationary denoise from the squelch-closed noise floor
--json                    # machine-readable output for tracking over time
```

Note: `--no-agc` is a deprecated alias for `--gain-mode off`. The decode/VAD/
prompt knobs above ride on the transcriber instance built for the run — pass
`--json` to record which ones were set (echoed under a top-level `"config"`
key) so an A/B run is self-describing.

`--noise-profile auto` mirrors the server's `stt_noise_profile` toggle: per
file it replays a captured `noise.wav` beside the WAV when present (written
by debug capture when the toggle is on), otherwise derives a clip live from
closed-squelch spans in the recording, otherwise runs without a clip —
exactly today's self-estimating denoise. Utterances without a clip are
counted (`noise_profile_fallbacks` in `--json`) so a run shows its real
coverage. Pre-roll audio is never used as a profile: it is carrier-open
audio and a wrong stationary estimate over-subtracts speech.

A/B comparison with different gain modes:

```bash
python -m backend.tools.eval_stt --audio /data/debug/stt --gain-mode rms --json > rms.json
python -m backend.tools.eval_stt --audio /data/debug/stt --gain-mode off --json > nogain.json
```

Unlabelled captures are skipped and counted in the summary. Compare corpus
WER between runs on the *same* capture set; re-run after every pipeline
change and record the number before merging.
