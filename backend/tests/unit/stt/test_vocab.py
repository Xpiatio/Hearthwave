import logging

from backend.stt import vocab


def test_curated_core_is_nato_plus_procedure():
    # NATO fully present
    assert "Alfa" in vocab.CURATED and "Zulu" in vocab.CURATED
    # key procedure words / Q-codes present
    for t in ("over", "roger", "say again", "standing by", "QSL", "CQ"):
        assert t in vocab.CURATED
    # CB slang and band-identifier extras were dropped from the core
    for t in ("breaker", "kerchunk", "MURS", "good buddy", "ratchet jaw"):
        assert t not in vocab.CURATED
    assert len(vocab.CURATED) == 40


def test_callsigns_come_last_so_they_survive_tail_trim():
    out = vocab.assemble_phrases(["KE8AAA", "KE8BBB"], ["my custom"], max_callsigns=100)
    assert out[-2:] == ["KE8AAA", "KE8BBB"]
    assert out.index("my custom") < out.index("KE8AAA")
    assert out.index("Alfa") < out.index("my custom")   # curated ranks below saved


def test_dedup_keeps_highest_priority_occurrence():
    # "QSL" is curated; if it's also a saved phrase it should appear once,
    # at the later (higher-priority) position — after the curated block.
    out = vocab.assemble_phrases([], ["QSL"], max_callsigns=100)
    assert out.count("QSL") == 1
    # the surviving QSL is the saved-phrase one (after the curated block start)
    assert out.index("QSL") > out.index("Alfa")


def test_callsign_cap_keeps_newest_and_logs(caplog):
    calls = [f"K{i:04d}" for i in range(105)]
    with caplog.at_level(logging.INFO):
        out = vocab.assemble_phrases(calls, [], max_callsigns=100)
    tail = out[-100:]
    assert tail == calls[-100:]          # newest (file-order tail) kept
    assert "K0000" not in out            # oldest dropped
    assert any("dropped 5" in r.message for r in caplog.records)
