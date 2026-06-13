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
--no-agc --no-lowpass     # isolate individual DSP stages
--model medium.en         # bigger model on identical audio
--vad-threshold 0.35      # earlier VAD onset in noise
--squelch-threshold 0.03  # weaker-carrier pre-trigger
--min-speech-s 0.25       # do short replies ("copy") survive?
--json                    # machine-readable output for tracking over time
```

Unlabelled captures are skipped and counted in the summary. Compare corpus
WER between runs on the *same* capture set; re-run after every pipeline
change and record the number before merging.
