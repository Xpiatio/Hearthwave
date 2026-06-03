"""Unit tests for backend.plugins.ncs.

Tests constructor, audio buffer behavior, on_client_message_received dispatch,
_fetch_nws_alerts_sync (mocked urllib), roster logic, and TX gating.

Anything requiring a live asyncio server, real network, or background tasks that
run forever is either mocked out or skipped.
"""
from __future__ import annotations

import asyncio
import collections
import json
import struct
import unittest.mock as mock
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.plugins.ncs import NCSPlugin, _fetch_nws_alerts_sync, _SAMPLE_RATE, _REPLAY_SECONDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(**kwargs) -> SimpleNamespace:
    defaults = dict(
        ncs_zone="MIZ071",
        ncs_announcement_interval=600,
        callsign="W8TST",
        location="West Michigan",
        name="Test NCS",
        journals_dir="/tmp/journals",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_ncs(config=None, channel_clear=True) -> NCSPlugin:
    """Construct an NCSPlugin with all dependencies mocked."""
    broadcast_fn = AsyncMock()
    tx_queue = asyncio.Queue()
    cfg = config or make_config()
    config_getter = MagicMock(return_value=cfg)
    channel_clear_fn = MagicMock(return_value=channel_clear)
    return NCSPlugin(
        broadcast_fn=broadcast_fn,
        tx_queue=tx_queue,
        config_getter=config_getter,
        channel_clear_fn=channel_clear_fn,
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestNCSPluginConstructor:
    def test_initial_state_inactive(self):
        ncs = make_ncs()
        assert ncs._active is False

    def test_roster_starts_empty(self):
        ncs = make_ncs()
        assert ncs._roster == {}

    def test_session_rx_starts_empty(self):
        ncs = make_ncs()
        assert ncs._session_rx == []

    def test_break_break_pending_false(self):
        ncs = make_ncs()
        assert ncs._break_break_pending is False

    def test_audio_buffer_starts_empty(self):
        ncs = make_ncs()
        assert len(ncs._audio_buffer) == 0
        assert ncs._audio_buffer_bytes == 0

    def test_audio_max_bytes_matches_constants(self):
        from backend.plugins.ncs import _BYTES_PER_SAMPLE
        ncs = make_ncs()
        expected = _REPLAY_SECONDS * _SAMPLE_RATE * _BYTES_PER_SAMPLE
        assert ncs._audio_max_bytes == expected

    def test_nws_and_announce_tasks_initially_none(self):
        ncs = make_ncs()
        assert ncs._nws_task is None
        assert ncs._announce_task is None

    def test_seen_alerts_starts_empty(self):
        ncs = make_ncs()
        assert ncs._seen_alerts == set()


# ---------------------------------------------------------------------------
# on_audio_rx_chunk — rolling buffer
# ---------------------------------------------------------------------------

class TestAudioRxChunkBuffer:
    def test_bytes_chunk_appended(self):
        ncs = make_ncs()
        chunk = b"\x00\x01\x02\x03"
        ncs.on_audio_rx_chunk(chunk)
        assert ncs._audio_buffer_bytes == 4
        assert len(ncs._audio_buffer) == 1

    def test_bytearray_chunk_appended(self):
        ncs = make_ncs()
        ncs.on_audio_rx_chunk(bytearray(b"\xAA\xBB"))
        assert ncs._audio_buffer_bytes == 2

    def test_multiple_chunks_accumulate(self):
        ncs = make_ncs()
        ncs.on_audio_rx_chunk(b"\x00" * 100)
        ncs.on_audio_rx_chunk(b"\x01" * 200)
        assert ncs._audio_buffer_bytes == 300
        assert len(ncs._audio_buffer) == 2

    def test_buffer_cap_evicts_oldest_chunks(self):
        """When total bytes exceed the cap, old chunks are popped from the left."""
        ncs = make_ncs()
        # Each chunk is half the max; three chunks should leave only the two most recent.
        half_max = ncs._audio_max_bytes // 2
        chunk_a = b"\xAA" * half_max
        chunk_b = b"\xBB" * half_max
        chunk_c = b"\xCC" * half_max
        ncs.on_audio_rx_chunk(chunk_a)
        ncs.on_audio_rx_chunk(chunk_b)
        ncs.on_audio_rx_chunk(chunk_c)
        # After eviction, total should be <= max_bytes
        assert ncs._audio_buffer_bytes <= ncs._audio_max_bytes
        # The earliest chunk (all \xAA) should have been dropped
        combined = b"".join(ncs._audio_buffer)
        assert b"\xAA" * half_max not in combined

    def test_buffer_byte_count_stays_consistent(self):
        ncs = make_ncs()
        for i in range(10):
            ncs.on_audio_rx_chunk(bytes([i]) * 1000)
        # byte count must always equal sum of actual buffer chunk lengths
        expected = sum(len(c) for c in ncs._audio_buffer)
        assert ncs._audio_buffer_bytes == expected

    def test_unconvertible_chunk_is_silently_ignored(self):
        """An object that can't be converted to bytes should not crash the hot path."""
        ncs = make_ncs()

        class Unconvertible:
            def __bytes__(self):
                raise ValueError("no bytes")

        # Should not raise
        ncs.on_audio_rx_chunk(Unconvertible())
        # Buffer unchanged
        assert ncs._audio_buffer_bytes == 0

    def test_numpy_like_array_is_accepted(self):
        """Simulates a numpy array (has __bytes__ via bytes())."""
        import struct
        # Build a float32 array as raw bytes
        samples = struct.pack("4f", 0.0, 0.5, -0.5, 1.0)
        ncs = make_ncs()
        ncs.on_audio_rx_chunk(samples)
        assert ncs._audio_buffer_bytes == len(samples)


# ---------------------------------------------------------------------------
# on_rx_final — transcript accumulation
# ---------------------------------------------------------------------------

class TestOnRxFinal:
    async def test_appends_text_when_active(self):
        ncs = make_ncs()
        ncs._active = True
        await ncs.on_rx_final("W8TST this is KD9XYZ over")
        assert ncs._session_rx == ["W8TST this is KD9XYZ over"]

    async def test_ignores_text_when_inactive(self):
        ncs = make_ncs()
        ncs._active = False
        await ncs.on_rx_final("some text")
        assert ncs._session_rx == []

    async def test_strips_whitespace(self):
        ncs = make_ncs()
        ncs._active = True
        await ncs.on_rx_final("  hello  ")
        assert ncs._session_rx == ["hello"]

    async def test_ignores_blank_text(self):
        ncs = make_ncs()
        ncs._active = True
        await ncs.on_rx_final("   ")
        assert ncs._session_rx == []

    async def test_multiple_transcripts_accumulate(self):
        ncs = make_ncs()
        ncs._active = True
        await ncs.on_rx_final("first")
        await ncs.on_rx_final("second")
        assert ncs._session_rx == ["first", "second"]


# ---------------------------------------------------------------------------
# on_audio_tx_pre_queue — BREAK BREAK gating
# ---------------------------------------------------------------------------

class TestTxPreQueue:
    async def test_passes_payload_when_not_pending(self):
        ncs = make_ncs()
        ncs._break_break_pending = False
        payload = {"text": "test"}
        result = await ncs.on_audio_tx_pre_queue(payload)
        assert result is payload

    async def test_blocks_tx_when_break_break_pending(self):
        ncs = make_ncs()
        ncs._break_break_pending = True
        result = await ncs.on_audio_tx_pre_queue({"text": "blocked"})
        assert result is None


# ---------------------------------------------------------------------------
# on_client_message_received — routing
# ---------------------------------------------------------------------------

class TestClientMessageRouting:
    async def test_unknown_type_does_nothing(self):
        ncs = make_ncs()
        # Should not raise
        await ncs.on_client_message_received({"type": "totally_unknown_type"})

    async def test_missing_type_does_nothing(self):
        ncs = make_ncs()
        await ncs.on_client_message_received({})

    async def test_ncs_get_state_calls_reply(self):
        ncs = make_ncs()
        reply = AsyncMock()
        await ncs.on_client_message_received({"type": "ncs_get_state"}, reply=reply)
        reply.assert_awaited_once()
        msg = reply.call_args[0][0]
        assert msg["type"] == "ncs_state"

    async def test_ncs_get_state_no_reply_does_not_raise(self):
        ncs = make_ncs()
        await ncs.on_client_message_received({"type": "ncs_get_state"}, reply=None)

    async def test_ncs_start_activates(self):
        ncs = make_ncs()
        # Patch away background tasks so they don't actually run; close coroutines
        # passed in to avoid "coroutine never awaited" warnings.
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs.on_client_message_received({"type": "ncs_start"})
        assert ncs._active is True

    async def test_ncs_end_deactivates(self):
        ncs = make_ncs()
        ncs._active = True
        # Prevent journal task creation; close coroutines to avoid warnings.
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs.on_client_message_received({"type": "ncs_end"})
        assert ncs._active is False

    async def test_ncs_checkin_adds_to_roster(self):
        ncs = make_ncs()
        await ncs.on_client_message_received(
            {"type": "ncs_checkin", "callsign": "kd9xyz", "traffic": "Routine", "name": "Alice", "location": "GR"}
        )
        assert "KD9XYZ" in ncs._roster
        entry = ncs._roster["KD9XYZ"]
        assert entry["callsign"] == "KD9XYZ"
        assert entry["status"] == "CheckedIn"
        assert entry["name"] == "Alice"
        assert entry["location"] == "GR"

    async def test_ncs_checkin_empty_callsign_ignored(self):
        ncs = make_ncs()
        await ncs.on_client_message_received({"type": "ncs_checkin", "callsign": "  "})
        assert ncs._roster == {}

    async def test_ncs_checkin_normalizes_callsign_to_uppercase(self):
        ncs = make_ncs()
        await ncs.on_client_message_received({"type": "ncs_checkin", "callsign": "w8tst"})
        assert "W8TST" in ncs._roster

    async def test_ncs_status_update_changes_status(self):
        ncs = make_ncs()
        # Pre-populate roster
        ncs._roster["W8TST"] = {
            "callsign": "W8TST", "status": "CheckedIn",
            "traffic": "Routine", "name": "", "location": "", "checkin_time": 0,
        }
        await ncs.on_client_message_received(
            {"type": "ncs_status_update", "callsign": "W8TST", "status": "Standby"}
        )
        assert ncs._roster["W8TST"]["status"] == "Standby"

    async def test_ncs_status_update_invalid_status_ignored(self):
        ncs = make_ncs()
        ncs._roster["W8TST"] = {
            "callsign": "W8TST", "status": "CheckedIn",
            "traffic": "Routine", "name": "", "location": "", "checkin_time": 0,
        }
        await ncs.on_client_message_received(
            {"type": "ncs_status_update", "callsign": "W8TST", "status": "INVALID"}
        )
        assert ncs._roster["W8TST"]["status"] == "CheckedIn"

    async def test_ncs_status_update_unknown_callsign_ignored(self):
        ncs = make_ncs()
        # Should not raise even if callsign not in roster
        await ncs.on_client_message_received(
            {"type": "ncs_status_update", "callsign": "NOCALL", "status": "Standby"}
        )
        assert "NOCALL" not in ncs._roster

    async def test_ncs_remove_deletes_from_roster(self):
        ncs = make_ncs()
        ncs._roster["W8TST"] = {
            "callsign": "W8TST", "status": "CheckedIn",
            "traffic": "Routine", "name": "", "location": "", "checkin_time": 0,
        }
        await ncs.on_client_message_received({"type": "ncs_remove", "callsign": "W8TST"})
        assert "W8TST" not in ncs._roster

    async def test_ncs_remove_unknown_callsign_does_not_raise(self):
        ncs = make_ncs()
        await ncs.on_client_message_received({"type": "ncs_remove", "callsign": "NOCALL"})

    async def test_ncs_break_break_creates_task(self):
        ncs = make_ncs()
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return) as mock_create:
            await ncs.on_client_message_received({"type": "ncs_break_break"})
        mock_create.assert_called_once()
        assert mock_create.call_args[1].get("name") == "ncs-break-break"

    async def test_ncs_get_replay_no_reply_does_not_raise(self):
        ncs = make_ncs()
        await ncs.on_client_message_received({"type": "ncs_get_replay"}, reply=None)


# ---------------------------------------------------------------------------
# _build_state_msg
# ---------------------------------------------------------------------------

class TestBuildStateMsg:
    def test_returns_correct_type(self):
        ncs = make_ncs()
        msg = ncs._build_state_msg()
        assert msg["type"] == "ncs_state"

    def test_active_field_matches_state(self):
        ncs = make_ncs()
        ncs._active = True
        assert ncs._build_state_msg()["active"] is True
        ncs._active = False
        assert ncs._build_state_msg()["active"] is False

    def test_roster_field_is_list(self):
        ncs = make_ncs()
        ncs._roster["W8TST"] = {
            "callsign": "W8TST", "status": "CheckedIn",
            "traffic": "Routine", "name": "", "location": "", "checkin_time": 0,
        }
        msg = ncs._build_state_msg()
        assert isinstance(msg["roster"], list)
        assert msg["roster"][0]["callsign"] == "W8TST"

    def test_zone_from_config(self):
        cfg = make_config(ncs_zone="MIZ071")
        ncs = make_ncs(config=cfg)
        msg = ncs._build_state_msg()
        assert msg["zone"] == "MIZ071"


# ---------------------------------------------------------------------------
# _handle_checkin
# ---------------------------------------------------------------------------

class TestHandleCheckin:
    async def test_new_checkin_added_to_roster(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Routine", "Bob", "GR")
        assert "W8TST" in ncs._roster
        assert ncs._roster["W8TST"]["traffic"] == "Routine"

    async def test_invalid_traffic_defaults_to_routine(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "NotReal", "", "")
        assert ncs._roster["W8TST"]["traffic"] == "Routine"

    async def test_emergency_traffic_accepted(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Emergency", "", "")
        assert ncs._roster["W8TST"]["traffic"] == "Emergency"

    async def test_priority_traffic_accepted(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Priority", "", "")
        assert ncs._roster["W8TST"]["traffic"] == "Priority"

    async def test_recheckin_preserves_original_checkin_time(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Routine", "", "")
        original_time = ncs._roster["W8TST"]["checkin_time"]
        await ncs._handle_checkin("W8TST", "Priority", "NewName", "")
        assert ncs._roster["W8TST"]["checkin_time"] == original_time

    async def test_recheckin_updates_name_if_provided(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Routine", "", "")
        await ncs._handle_checkin("W8TST", "Routine", "Alice", "")
        assert ncs._roster["W8TST"]["name"] == "Alice"

    async def test_recheckin_preserves_existing_name_if_empty(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Routine", "Bob", "")
        await ncs._handle_checkin("W8TST", "Routine", "", "")
        assert ncs._roster["W8TST"]["name"] == "Bob"

    async def test_broadcasts_roster_after_checkin(self):
        ncs = make_ncs()
        await ncs._handle_checkin("W8TST", "Routine", "", "")
        ncs._broadcast.assert_awaited()


# ---------------------------------------------------------------------------
# _fetch_nws_alerts_sync — mocked urllib
# ---------------------------------------------------------------------------

class TestFetchNwsAlertsSync:
    def test_returns_features_list_on_success(self):
        fake_response_data = json.dumps({
            "features": [
                {"id": "abc123", "properties": {"event": "Tornado Warning", "severity": "Extreme"}}
            ]
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = fake_response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("backend.plugins.ncs.urllib.request.urlopen", return_value=mock_response):
            result = _fetch_nws_alerts_sync("MIZ071")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "abc123"

    def test_returns_empty_list_on_network_error(self):
        with patch("backend.plugins.ncs.urllib.request.urlopen", side_effect=OSError("timeout")):
            result = _fetch_nws_alerts_sync("MIZ071")
        assert result == []

    def test_returns_empty_list_on_json_error(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json at all {{{"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("backend.plugins.ncs.urllib.request.urlopen", return_value=mock_response):
            result = _fetch_nws_alerts_sync("MIZ071")
        assert result == []

    def test_empty_features_array(self):
        fake_response_data = json.dumps({"features": []}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("backend.plugins.ncs.urllib.request.urlopen", return_value=mock_response):
            result = _fetch_nws_alerts_sync("MIZ071")
        assert result == []

    def test_missing_features_key_returns_empty_list(self):
        fake_response_data = json.dumps({"type": "FeatureCollection"}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("backend.plugins.ncs.urllib.request.urlopen", return_value=mock_response):
            result = _fetch_nws_alerts_sync("MIZ071")
        assert result == []


# ---------------------------------------------------------------------------
# _poll_nws_once — alert dispatching logic
# ---------------------------------------------------------------------------

class TestPollNwsOnce:
    async def test_broadcasts_new_alert(self):
        ncs = make_ncs()
        features = [
            {
                "id": "alert-1",
                "properties": {
                    "id": "alert-1",
                    "event": "Tornado Warning",
                    "severity": "Extreme",
                    "headline": "Tornado Warning in effect",
                },
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        ncs._broadcast.assert_awaited()
        call_args = ncs._broadcast.call_args_list[0][0][0]
        assert call_args["type"] == "ncs_alert"
        assert call_args["id"] == "alert-1"

    async def test_skips_already_seen_alert(self):
        ncs = make_ncs()
        ncs._seen_alerts.add("alert-1")
        features = [
            {
                "id": "alert-1",
                "properties": {"id": "alert-1", "event": "Test", "severity": "Minor", "headline": "Test"},
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        ncs._broadcast.assert_not_awaited()

    async def test_extreme_alert_queues_tx_when_channel_clear(self):
        ncs = make_ncs(channel_clear=True)
        features = [
            {
                "id": "alert-extreme",
                "properties": {
                    "id": "alert-extreme",
                    "event": "Tornado Warning",
                    "severity": "Extreme",
                    "headline": "Tornado Warning in effect",
                },
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        assert not ncs._tx_queue.empty()
        item = ncs._tx_queue.get_nowait()
        assert "SKYWARN" in item["text"]

    async def test_severe_alert_queues_tx(self):
        ncs = make_ncs(channel_clear=True)
        features = [
            {
                "id": "alert-severe",
                "properties": {
                    "id": "alert-severe",
                    "event": "Severe Thunderstorm Warning",
                    "severity": "Severe",
                    "headline": "Severe Thunderstorm Warning",
                },
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        assert not ncs._tx_queue.empty()

    async def test_minor_alert_does_not_queue_tx(self):
        ncs = make_ncs(channel_clear=True)
        features = [
            {
                "id": "alert-minor",
                "properties": {
                    "id": "alert-minor",
                    "event": "Small Craft Advisory",
                    "severity": "Minor",
                    "headline": "Small Craft Advisory",
                },
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        assert ncs._tx_queue.empty()

    async def test_extreme_alert_does_not_queue_tx_when_channel_busy(self):
        ncs = make_ncs(channel_clear=False)
        features = [
            {
                "id": "alert-busy",
                "properties": {
                    "id": "alert-busy",
                    "event": "Tornado Warning",
                    "severity": "Extreme",
                    "headline": "Tornado Warning in effect",
                },
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        # Alert should be broadcast but TX should NOT be queued
        assert ncs._tx_queue.empty()

    async def test_alert_added_to_seen_set(self):
        ncs = make_ncs()
        features = [
            {
                "id": "alert-seen",
                "properties": {"id": "alert-seen", "event": "Test", "severity": "Minor", "headline": "Test"},
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        assert "alert-seen" in ncs._seen_alerts

    async def test_alert_without_properties_id_uses_feature_id(self):
        ncs = make_ncs()
        features = [
            {
                "id": "feature-level-id",
                "properties": {"event": "Test", "severity": "Minor", "headline": "Test"},
            }
        ]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        assert "feature-level-id" in ncs._seen_alerts

    async def test_alert_with_no_id_is_skipped(self):
        ncs = make_ncs()
        features = [{"properties": {"event": "Test", "severity": "Minor", "headline": "Test"}}]
        with patch("backend.plugins.ncs._fetch_nws_alerts_sync", return_value=features):
            await ncs._poll_nws_once("MIZ071")

        ncs._broadcast.assert_not_awaited()


# ---------------------------------------------------------------------------
# _handle_start / _handle_end
# ---------------------------------------------------------------------------

class TestHandleStartEnd:
    async def test_handle_start_sets_active(self):
        ncs = make_ncs()
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock(cancel=MagicMock())
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_start()
        assert ncs._active is True

    async def test_handle_start_clears_roster(self):
        ncs = make_ncs()
        ncs._roster["OLD"] = {}
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock(cancel=MagicMock())
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_start()
        assert ncs._roster == {}

    async def test_handle_start_clears_session_rx(self):
        ncs = make_ncs()
        ncs._session_rx.append("old line")
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock(cancel=MagicMock())
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_start()
        assert ncs._session_rx == []

    async def test_handle_start_idempotent(self):
        """Calling _handle_start when already active does nothing."""
        ncs = make_ncs()
        ncs._active = True
        ncs._roster["X"] = {}
        await ncs._handle_start()
        assert "X" in ncs._roster  # roster not cleared

    async def test_handle_end_sets_inactive(self):
        ncs = make_ncs()
        ncs._active = True
        # No tasks to cancel; close journal coroutine to avoid warning
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_end()
        assert ncs._active is False

    async def test_handle_end_when_inactive_is_noop(self):
        ncs = make_ncs()
        ncs._active = False
        await ncs._handle_end()
        ncs._broadcast.assert_not_awaited()

    async def test_handle_end_broadcasts_state(self):
        ncs = make_ncs()
        ncs._active = True
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_end()
        ncs._broadcast.assert_awaited()
        msg = ncs._broadcast.call_args[0][0]
        assert msg["type"] == "ncs_state"
        assert msg["active"] is False

    async def test_handle_end_cancels_running_tasks(self):
        """Tasks stored on the plugin instance should be cancelled on end."""
        ncs = make_ncs()
        ncs._active = True
        mock_nws_task = MagicMock()
        mock_announce_task = MagicMock()
        ncs._nws_task = mock_nws_task
        ncs._announce_task = mock_announce_task
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_end()
        mock_nws_task.cancel.assert_called_once()
        mock_announce_task.cancel.assert_called_once()

    async def test_handle_end_creates_journal_task_when_data_exists(self):
        ncs = make_ncs()
        ncs._active = True
        ncs._session_rx.append("a line")
        created_tasks = []
        def _close_and_return(coro, **kwargs):
            coro.close()
            m = MagicMock()
            created_tasks.append(kwargs.get("name"))
            return m
        with patch.object(asyncio, "create_task", side_effect=_close_and_return):
            await ncs._handle_end()
        assert "ncs-journal" in created_tasks


# ---------------------------------------------------------------------------
# _handle_break_break
# ---------------------------------------------------------------------------

class TestHandleBreakBreak:
    async def test_sets_and_clears_pending_flag(self):
        ncs = make_ncs()
        # Run the full coroutine (it has asyncio.sleep(2.0) — patch it out)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ncs._handle_break_break()
        assert ncs._break_break_pending is False

    async def test_broadcasts_ack(self):
        ncs = make_ncs()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ncs._handle_break_break()
        calls = [c[0][0] for c in ncs._broadcast.call_args_list]
        types_broadcast = [c["type"] for c in calls]
        assert "ncs_break_break_ack" in types_broadcast
        assert "tx_status" in types_broadcast

    async def test_drains_tx_queue(self):
        ncs = make_ncs()
        await ncs._tx_queue.put({"text": "item1"})
        await ncs._tx_queue.put({"text": "item2"})
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ncs._handle_break_break()
        assert ncs._tx_queue.empty()

    async def test_empty_queue_does_not_raise(self):
        ncs = make_ncs()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ncs._handle_break_break()


# ---------------------------------------------------------------------------
# _handle_get_replay
# ---------------------------------------------------------------------------

class TestHandleGetReplay:
    async def test_empty_buffer_returns_empty_data(self):
        ncs = make_ncs()
        reply = AsyncMock()
        await ncs._handle_get_replay(reply)
        reply.assert_awaited_once()
        msg = reply.call_args[0][0]
        assert msg["type"] == "ncs_replay_audio"
        assert msg["data"] == ""

    async def test_buffer_with_data_returns_b64(self):
        ncs = make_ncs()
        # Put 4 float32 samples into the buffer
        import struct, base64
        samples = struct.pack("4f", 0.0, 0.5, -0.5, 1.0)
        ncs._audio_buffer.append(samples)
        ncs._audio_buffer_bytes = len(samples)
        reply = AsyncMock()
        try:
            await ncs._handle_get_replay(reply)
        except ImportError:
            pytest.skip("numpy not available")
        reply.assert_awaited_once()
        msg = reply.call_args[0][0]
        assert msg["type"] == "ncs_replay_audio"
        assert msg["sample_rate"] == _SAMPLE_RATE

    async def test_numpy_import_failure_returns_empty_data(self):
        ncs = make_ncs()
        ncs._audio_buffer.append(b"\x00" * 16)
        ncs._audio_buffer_bytes = 16
        reply = AsyncMock()
        with patch.dict("sys.modules", {"numpy": None}):
            await ncs._handle_get_replay(reply)
        reply.assert_awaited_once()
        msg = reply.call_args[0][0]
        assert msg["data"] == ""


# ---------------------------------------------------------------------------
# ncs_get_replay via on_client_message_received (line 127)
# ---------------------------------------------------------------------------

class TestClientMessageGetReplay:
    async def test_ncs_get_replay_with_reply_creates_task(self):
        ncs = make_ncs()
        reply = AsyncMock()
        def _close_and_return(coro, **kwargs):
            coro.close()
            return MagicMock()
        with patch.object(asyncio, "create_task", side_effect=_close_and_return) as mock_create:
            await ncs.on_client_message_received({"type": "ncs_get_replay"}, reply=reply)
        mock_create.assert_called_once()
        assert mock_create.call_args[1].get("name") == "ncs-replay"


# ---------------------------------------------------------------------------
# _save_ncs_journal
# ---------------------------------------------------------------------------

class TestSaveNcsJournal:
    async def test_calls_save_journal_and_broadcasts(self):
        ncs = make_ncs()
        ncs._roster["W8TST"] = {
            "callsign": "W8TST", "status": "CheckedIn",
            "traffic": "Routine", "name": "Alice", "location": "GR", "checkin_time": 0,
        }
        ncs._session_rx.append("a line")
        # save_journal is imported inside _save_ncs_journal via
        # `from backend.persistence.journal import save_journal`, so patch the
        # module object that will be imported.
        mock_journal_mod = mock.MagicMock()
        mock_journal_mod.save_journal.return_value = "/tmp/journal.md"
        with patch.dict("sys.modules", {"backend.persistence.journal": mock_journal_mod}):
            await ncs._save_ncs_journal()
        ncs._broadcast.assert_awaited()

    async def test_journal_save_failure_is_caught(self):
        ncs = make_ncs()
        mock_journal_mod = mock.MagicMock()
        mock_journal_mod.save_journal.side_effect = OSError("disk full")
        with patch.dict("sys.modules", {"backend.persistence.journal": mock_journal_mod}):
            # Must not propagate
            await ncs._save_ncs_journal()


# ---------------------------------------------------------------------------
# _nws_poll_loop (light — test cancellation handling)
# ---------------------------------------------------------------------------

class TestNwsPollLoop:
    async def test_loop_exits_on_cancelled_error(self):
        ncs = make_ncs()
        ncs._active = True
        # Make _poll_nws_once raise CancelledError immediately
        async def cancel_immediately(zone):
            raise asyncio.CancelledError()

        ncs._poll_nws_once = cancel_immediately
        # Should return cleanly (not re-raise)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ncs._nws_poll_loop()

    async def test_loop_continues_after_generic_exception(self):
        """A non-CancelledError exception in _poll_nws_once is swallowed; loop stops via _active."""
        ncs = make_ncs()
        ncs._active = True
        call_count = 0

        async def fail_then_stop(zone):
            nonlocal call_count
            call_count += 1
            ncs._active = False  # stop after first iteration
            raise RuntimeError("poll failed")

        ncs._poll_nws_once = fail_then_stop
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ncs._nws_poll_loop()
        assert call_count == 1


# ---------------------------------------------------------------------------
# _announcement_loop (light — test cancellation handling)
# ---------------------------------------------------------------------------

class TestAnnouncementLoop:
    async def test_loop_exits_on_cancelled_error(self):
        ncs = make_ncs()
        ncs._active = True
        call_count = 0

        async def fake_sleep(interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                # Deactivate after first real iteration to break the while loop
                ncs._active = False

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await ncs._announcement_loop(0)
        # We should reach here without hanging

    async def test_announcement_queues_tx_when_channel_clear(self):
        ncs = make_ncs(channel_clear=True)
        ncs._active = True
        sleep_calls = []

        async def fake_sleep(interval):
            sleep_calls.append(interval)
            # Deactivate on the *second* sleep call.
            # The loop is: initial sleep → while active: (body) → end sleep.
            # We want the body to execute once, so we deactivate on the end-of-loop sleep.
            if len(sleep_calls) >= 2:
                ncs._active = False

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await ncs._announcement_loop(0)

        assert not ncs._tx_queue.empty()
        item = ncs._tx_queue.get_nowait()
        assert "Net Control" in item["text"]

    async def test_announcement_skips_tx_when_channel_busy(self):
        ncs = make_ncs(channel_clear=False)
        ncs._active = True

        async def fake_sleep(interval):
            ncs._active = False

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await ncs._announcement_loop(0)

        assert ncs._tx_queue.empty()

    async def test_loop_exits_cleanly_on_cancelled_error(self):
        """CancelledError inside the loop body causes the loop to return."""
        ncs = make_ncs()
        ncs._active = True
        call_count = 0

        async def fake_sleep(interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return  # let the while-loop body run
            raise asyncio.CancelledError()

        # Make _channel_clear raise CancelledError on first call inside the body
        def channel_raises():
            raise asyncio.CancelledError()

        ncs._channel_clear = channel_raises
        with patch("asyncio.sleep", side_effect=fake_sleep):
            await ncs._announcement_loop(0)

    async def test_loop_swallows_generic_exception_in_body(self):
        """A non-CancelledError exception in the loop body is logged and execution continues."""
        ncs = make_ncs()
        ncs._active = True
        call_count = 0

        async def fake_sleep(interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                ncs._active = False

        def channel_raises():
            raise OSError("channel check failed")

        ncs._channel_clear = channel_raises
        with patch("asyncio.sleep", side_effect=fake_sleep):
            await ncs._announcement_loop(0)
