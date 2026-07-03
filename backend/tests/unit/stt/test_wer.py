"""Tests for backend.stt.wer — shared WER normalization/scoring.

Extracted from backend.tools.eval_stt so the calibration wizard and the CLI
eval harness score identically by construction.
"""
import pytest

from backend.stt.wer import normalize_text, score


def test_normalize_text_strips_case_and_punctuation():
    assert normalize_text("Hello, World!  Over.") == "hello world over"


def test_score_zero_wer_for_equivalent_text():
    result = score(["Radio check, over!"], ["radio check over"])
    assert result["wer"] == 0.0


def test_score_counts_errors():
    result = score(["alpha bravo charlie delta"], ["alpha bravo charlie echo"])
    assert result["wer"] == pytest.approx(0.25)


def test_score_reports_count():
    result = score(["a", "b"], ["a", "c"])
    assert result["count"] == 2
