def load_vad_model():
    """Load the bundled Silero VAD ONNX model. Lazy-imported so the heavy
    silero-vad package doesn't run at app boot — only when listening starts."""
    from silero_vad import load_silero_vad

    return load_silero_vad()


def make_vad_iterator(
    vad_model,
    sample_rate,
    threshold,
    min_silence_duration_ms=500,
    speech_pad_ms=200,
):
    """Build a configured VADIterator. Wrapping the constructor keeps the
    silero-vad import lazy and lets callers stay free of the dependency."""
    from silero_vad import VADIterator

    return VADIterator(
        vad_model,
        sampling_rate=sample_rate,
        threshold=threshold,
        min_silence_duration_ms=min_silence_duration_ms,
        speech_pad_ms=speech_pad_ms,
    )


def reset_vad_state(vad_iter):
    """Reset VAD internal state across a TX pause boundary so an in-progress
    speech segment doesn't bleed across into the resumed listen window."""
    try:
        vad_iter.reset_states()
    except Exception:
        pass
