def pick_cut_index(peaks, start, end):
    """Return the index of the lowest-peak chunk in the half-open window
    [start, end). Used by the streaming-STT path to find a natural pause
    between words before slicing a long utterance off for partial
    transcription — cutting at a local minimum avoids slicing mid-syllable
    and lets each slice transcribe as a coherent run of words.

    Returns None when the window is empty, out of range, or has length 0.
    Ties resolve to the earliest index (Python's min-with-key is stable
    over the input order).
    """
    if not peaks:
        return None
    lo = max(0, int(start))
    hi = min(len(peaks), int(end))
    if hi <= lo:
        return None
    best_idx = lo
    best_val = peaks[lo]
    for idx in range(lo + 1, hi):
        if peaks[idx] < best_val:
            best_val = peaks[idx]
            best_idx = idx
    return best_idx
