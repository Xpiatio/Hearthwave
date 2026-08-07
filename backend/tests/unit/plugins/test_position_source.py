"""Unit tests for backend.plugins.position_source.

PositionPoller owns the poll-task lifecycle and the per-node dedupe so that
concrete sources (Meshtastic node DB, APRS TNC) only have to say what a poll
reads. These tests drive it with a fake read; the real sources need hardware.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from backend.plugins.context import PluginContext
from backend.plugins.position_source import MIN_POLL_SECONDS, PositionPoller


class FakeSource:
    """Stands in for the plugin that owns a poller."""

    def __init__(self, **poller_kwargs) -> None:
        self.reported: list[tuple] = []
        self.polls = 0
        self.opens = 0
        self.closes = 0
        self.poll_error: Exception | None = None
        self.open_error: Exception | None = None
        self.polled = asyncio.Event()
        self.report_result = True
        self.ctx = self._make_ctx()
        self.poller = PositionPoller(
            "fake",
            self._poll_once,
            ctx_getter=lambda: self.ctx,
            on_start=self._open,
            on_stop=self._close,
            **poller_kwargs,
        )

    def _make_ctx(self) -> PluginContext:
        async def _noop(*_a, **_k):
            return None

        async def _report(source, node_id, lat, lon, label="", **meta):
            self.reported.append((source, node_id, lat, lon, label, meta))
            return self.report_result

        return PluginContext(
            broadcast=_noop,
            enqueue_tx=_noop,
            get_config=dict,
            channel_clear=lambda: True,
            report_position=_report,
            data_dir=Path("/tmp"),
            logger=logging.getLogger("test.position_source"),
        )

    async def _open(self) -> None:
        if self.open_error is not None:
            raise self.open_error
        self.opens += 1

    async def _close(self) -> None:
        self.closes += 1

    async def _poll_once(self) -> None:
        self.polls += 1
        self.polled.set()
        if self.poll_error is not None:
            raise self.poll_error


@pytest.fixture
def source():
    return FakeSource()


async def _settle():
    """Let the poll task reach its first await without wall-clock sleeping."""
    for _ in range(5):
        await asyncio.sleep(0)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enabling_starts_a_single_poll_task(source):
    await source.poller.configure(enabled=True, poll_seconds=60)
    await source.poller.configure(enabled=True, poll_seconds=60)  # idempotent
    await source.polled.wait()
    assert source.opens == 1
    assert source.polls == 1
    await source.poller.stop()


@pytest.mark.asyncio
async def test_disabling_stops_and_closes(source):
    await source.poller.configure(enabled=True, poll_seconds=60)
    await source.polled.wait()
    await source.poller.configure(enabled=False, poll_seconds=60)
    assert source.poller.is_running is False
    assert source.closes == 1


@pytest.mark.asyncio
async def test_starting_disabled_never_polls(source):
    await source.poller.configure(enabled=False, poll_seconds=60)
    await _settle()
    assert source.polls == 0
    assert source.poller.is_running is False


@pytest.mark.asyncio
async def test_stop_is_safe_when_never_started(source):
    await source.poller.stop()
    assert source.poller.is_running is False


@pytest.mark.asyncio
async def test_a_failed_open_does_not_leave_a_running_loop(source):
    source.open_error = RuntimeError("no serial port")
    await source.poller.configure(enabled=True, poll_seconds=60)
    await _settle()
    assert source.polls == 0
    assert source.poller.is_running is False


@pytest.mark.asyncio
async def test_a_failing_poll_does_not_kill_the_loop(source):
    source.poll_error = RuntimeError("radio unplugged")
    await source.poller.configure(enabled=True, poll_seconds=0)
    # Interval is floored, so drive the retries by hand rather than waiting.
    while source.polls < 1:
        await asyncio.sleep(0)
    assert source.poller.is_running is True
    await source.poller.stop()


@pytest.mark.asyncio
async def test_poll_interval_is_floored(source):
    await source.poller.configure(enabled=False, poll_seconds=0.1)
    assert source.poller._poll_seconds == MIN_POLL_SECONDS


@pytest.mark.asyncio
async def test_reconfiguring_a_running_poller_retunes_without_restart(source):
    await source.poller.configure(enabled=True, poll_seconds=60)
    await source.polled.wait()
    await source.poller.configure(enabled=True, poll_seconds=120)
    assert source.poller._poll_seconds == 120
    assert source.opens == 1  # not torn down and reopened
    await source.poller.stop()


# ---------------------------------------------------------------------------
# Reporting / dedupe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_forwards_to_the_context(source):
    assert await source.poller.report("n1", 42.9, -85.8, label="Barn", alt_m=240) is True
    assert source.reported == [("fake", "n1", 42.9, -85.8, "Barn", {"alt_m": 240})]


@pytest.mark.asyncio
async def test_repeat_of_the_same_fix_is_suppressed(source):
    await source.poller.report("n1", 42.9, -85.8)
    assert await source.poller.report("n1", 42.9, -85.8) is False
    assert len(source.reported) == 1


@pytest.mark.asyncio
async def test_a_node_that_moved_is_always_reported(source):
    await source.poller.report("n1", 42.9, -85.8)
    assert await source.poller.report("n1", 42.91, -85.8) is True
    assert len(source.reported) == 2


@pytest.mark.asyncio
async def test_the_dedupe_window_can_be_disabled():
    src = FakeSource(min_report_interval_s=0.0)
    await src.poller.report("n1", 42.9, -85.8)
    assert await src.poller.report("n1", 42.9, -85.8) is True


@pytest.mark.asyncio
async def test_dedupe_is_per_node(source):
    await source.poller.report("n1", 42.9, -85.8)
    assert await source.poller.report("n2", 42.9, -85.8) is True


@pytest.mark.asyncio
async def test_blank_node_id_is_refused(source):
    assert await source.poller.report("  ", 42.9, -85.8) is False
    assert source.reported == []


@pytest.mark.asyncio
async def test_a_rejected_fix_is_not_remembered(source):
    source.report_result = False
    assert await source.poller.report("n1", 42.9, -85.8) is False
    assert source.poller._last_seen == {}


@pytest.mark.asyncio
async def test_report_without_a_context_is_a_no_op(source):
    source.ctx = None
    assert await source.poller.report("n1", 42.9, -85.8) is False


@pytest.mark.asyncio
async def test_dedupe_table_is_bounded(source, monkeypatch):
    monkeypatch.setattr("backend.plugins.position_source.MAX_TRACKED_NODES", 3)
    for i in range(6):
        await source.poller.report(f"n{i}", 42.9 + i / 1000, -85.8)
    assert len(source.poller._last_seen) == 3


@pytest.mark.asyncio
async def test_a_re_read_of_the_same_node_db_row_is_not_a_new_hearing(source):
    # Polling a node database every minute must not keep re-stamping a node
    # the radio last actually heard days ago.
    await source.poller.report("n1", 42.9, -85.8, heard_at=1_700_000_000)
    assert await source.poller.report("n1", 42.9, -85.8, heard_at=1_700_000_000) is False
    assert len(source.reported) == 1


@pytest.mark.asyncio
async def test_an_advancing_heard_at_reports_even_inside_the_rate_limit(source):
    # The station really was heard again, so its age must reset — the 10 s
    # window is for sources that can't tell us, not for ones that can.
    await source.poller.report("n1", 42.9, -85.8, heard_at=1_700_000_000)
    assert await source.poller.report("n1", 42.9, -85.8, heard_at=1_700_000_060) is True
    assert len(source.reported) == 2


@pytest.mark.asyncio
async def test_a_useless_heard_at_falls_back_to_the_rate_limit(source):
    # A radio with no clock reports 0; that is not a timestamp.
    await source.poller.report("n1", 42.9, -85.8, heard_at=0)
    assert await source.poller.report("n1", 42.9, -85.8, heard_at=0) is False


@pytest.mark.asyncio
async def test_stopping_clears_the_dedupe_table(source):
    await source.poller.report("n1", 42.9, -85.8)
    await source.poller.stop()
    assert source.poller._last_seen == {}
