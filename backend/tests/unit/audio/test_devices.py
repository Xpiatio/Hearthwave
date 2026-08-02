"""Tests for name-based audio device resolution.

PortAudio snapshots its device list at Pa_Initialize() and assigns positional
indices.  A card that is busy during that scan is omitted entirely, which
shifts every later index down by one — so a stored index silently starts
pointing at different hardware.  These tests pin the name-based behaviour that
replaces index storage.
"""
import pytest

from backend.audio import devices
from backend.audio.devices import DEFAULT as DEFAULT_IDX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def dev(name: str, *, ins: int = 0, outs: int = 0) -> dict:
    return {"name": name, "max_input_channels": ins, "max_output_channels": outs}


USB = dev("USB Audio: - (hw:0,0)", ins=2, outs=2)
HDMI0 = dev("HD-Audio Generic: HDMI 0 (hw:1,3)", outs=8)
ANALOG = dev("HD-Audio Generic: SN6140 Analog (hw:2,0)", ins=2, outs=2)


@pytest.fixture
def fake_devices(monkeypatch):
    """Install a fake PortAudio enumeration; returns a setter for the list."""
    def install(device_list):
        monkeypatch.setattr(devices, "_query", lambda: list(device_list))
        devices.invalidate_cache()
    yield install
    devices.invalidate_cache()


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

class TestResolve:
    def test_resolves_name_to_current_index(self, fake_devices):
        fake_devices([USB, HDMI0, ANALOG])
        assert devices.resolve(USB["name"], "output") == 0

    def test_index_shift_does_not_change_which_device_is_selected(self, fake_devices):
        """The actual bug: USB drops out of the scan, shifting indices down."""
        fake_devices([USB, HDMI0, ANALOG])
        assert devices.resolve(ANALOG["name"], "output") == 2

        # USB busy at scan time -> omitted -> everything shifts down one slot.
        fake_devices([HDMI0, ANALOG])
        assert devices.resolve(ANALOG["name"], "output") == 1

    def test_missing_device_resolves_to_system_default(self, fake_devices):
        fake_devices([HDMI0, ANALOG])
        assert devices.resolve(USB["name"], "output") == -1

    def test_system_default_sentinel_passes_through(self, fake_devices):
        fake_devices([USB, HDMI0])
        assert devices.resolve(-1, "output") == -1

    def test_output_only_device_is_not_resolvable_as_input(self, fake_devices):
        fake_devices([USB, HDMI0])
        assert devices.resolve(HDMI0["name"], "input") == -1

    def test_same_name_resolves_per_kind(self, fake_devices):
        fake_devices([HDMI0, USB])
        assert devices.resolve(USB["name"], "input") == 1
        assert devices.resolve(USB["name"], "output") == 1


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

class TestListDevices:
    def test_lists_only_devices_with_channels_of_that_kind(self, fake_devices):
        fake_devices([USB, HDMI0, ANALOG])
        names = [d["name"] for d in devices.list_devices("input")]
        assert names == [USB["name"], ANALOG["name"]]

    def test_entries_carry_name_as_id(self, fake_devices):
        fake_devices([USB, HDMI0])
        entry = devices.list_devices("output")[0]
        assert entry["id"] == USB["name"]
        assert entry["label"] == USB["name"]

    def test_enumeration_failure_yields_empty_list(self, monkeypatch):
        def boom():
            raise RuntimeError("PortAudio not initialised")
        monkeypatch.setattr(devices, "_query", boom)
        devices.invalidate_cache()
        assert devices.list_devices("output") == []


# ---------------------------------------------------------------------------
# Rescanning
# ---------------------------------------------------------------------------

class TestRefresh:
    def test_list_is_memoised_between_refreshes(self, monkeypatch):
        present = [HDMI0]
        monkeypatch.setattr(devices, "_query", lambda: list(present))
        devices.invalidate_cache()
        assert len(devices.list_devices("output")) == 1

        present.append(USB)  # card freed up, but nothing told us to re-scan
        assert len(devices.list_devices("output")) == 1

    def test_refresh_exposes_a_device_that_was_busy_at_startup(self, monkeypatch):
        present = [HDMI0]
        monkeypatch.setattr(devices, "_query", lambda: list(present))
        monkeypatch.setattr(devices, "_reinit", lambda: None)
        devices.invalidate_cache()
        assert devices.resolve(USB["name"], "output") == DEFAULT_IDX

        present.insert(0, USB)
        devices.refresh()
        assert devices.resolve(USB["name"], "output") == 0

    def test_refresh_reinitialises_portaudio(self, monkeypatch):
        """Clearing our own cache is not enough — PortAudio caches too."""
        calls = []
        monkeypatch.setattr(devices, "_reinit", lambda: calls.append("reinit"))
        monkeypatch.setattr(devices, "_query", lambda: [HDMI0])
        devices.refresh()
        assert calls == ["reinit"]

    def test_refresh_survives_a_failing_reinit(self, monkeypatch):
        def boom():
            raise RuntimeError("PortAudio busy")
        monkeypatch.setattr(devices, "_reinit", boom)
        monkeypatch.setattr(devices, "_query", lambda: [HDMI0])
        devices.refresh()
        assert [d["name"] for d in devices.list_devices("output")] == [HDMI0["name"]]
