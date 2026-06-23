"""Unit tests for backend.plugins.loader — discovery + (hot-)loading of plugins.

Fixture plugins are written to tmp dirs as plugin.py source and loaded through the
real importlib path, so this exercises the actual load/reload/unload machinery.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from backend.plugins import loader
from backend.plugins.context import PluginContext
from backend.plugins.registry import PluginRegistry


def make_ctx() -> PluginContext:
    async def _noop(*_a, **_k):
        return None

    return PluginContext(
        broadcast=_noop,
        enqueue_tx=_noop,
        get_config=dict,
        channel_clear=lambda: True,
        data_dir=Path("/tmp"),
        logger=logging.getLogger("test.plugin"),
    )


def write_plugin(plugins_dir: Path, plugin_id: str, body: str) -> Path:
    d = plugins_dir / plugin_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "plugin.py").write_text(body, encoding="utf-8")
    return d


GOOD = '''
from backend.plugins.base import BasePlugin, PluginManifest
class GoodPlugin(BasePlugin):
    manifest = PluginManifest(id="{id}", name="Good", description="x", version="{ver}")
    async def setup(self):
        self.setup_ran = True
'''


class TestDiscover:
    def test_finds_dirs_with_plugin_py(self, tmp_path):
        write_plugin(tmp_path, "alpha", GOOD.format(id="alpha", ver="1"))
        write_plugin(tmp_path, "beta", GOOD.format(id="beta", ver="1"))
        (tmp_path / "not_a_plugin").mkdir()  # no plugin.py → ignored
        found = [p.name for p in loader.discover(tmp_path)]
        assert found == ["alpha", "beta"]

    def test_missing_dir_is_empty(self, tmp_path):
        assert loader.discover(tmp_path / "nope") == []


class TestLoad:
    async def test_loads_binds_ctx_and_registers(self, tmp_path):
        write_plugin(tmp_path, "good", GOOD.format(id="good", ver="1"))
        reg = PluginRegistry()
        inst = await loader.load_plugin(tmp_path / "good", make_ctx(), reg)
        assert inst is not None
        assert reg.get("good") is inst
        assert inst.ctx is not None  # bound before setup
        assert getattr(inst, "setup_ran", False) is True

    async def test_module_level_PLUGIN_instance(self, tmp_path):
        write_plugin(tmp_path, "inst", '''
from backend.plugins.base import BasePlugin, PluginManifest
class P(BasePlugin):
    manifest = PluginManifest(id="inst", name="Inst", description="x")
PLUGIN = P()
''')
        reg = PluginRegistry()
        inst = await loader.load_plugin(tmp_path / "inst", make_ctx(), reg)
        assert inst is not None and reg.get("inst") is inst

    async def test_get_plugin_factory(self, tmp_path):
        write_plugin(tmp_path, "fac", '''
from backend.plugins.base import BasePlugin, PluginManifest
class P(BasePlugin):
    manifest = PluginManifest(id="fac", name="Fac", description="x")
def get_plugin():
    return P()
''')
        reg = PluginRegistry()
        inst = await loader.load_plugin(tmp_path / "fac", make_ctx(), reg)
        assert inst is not None and reg.get("fac") is inst

    async def test_import_error_is_recorded_not_raised(self, tmp_path):
        write_plugin(tmp_path, "bad", "raise RuntimeError('boom at import')\n")
        reg = PluginRegistry()
        inst = await loader.load_plugin(tmp_path / "bad", make_ctx(), reg)
        assert inst is None
        manifests = reg.manifests({})
        err = next(m for m in manifests if m["id"] == "bad")
        assert "boom at import" in err["error"]

    async def test_setup_error_is_recorded(self, tmp_path):
        write_plugin(tmp_path, "setupfail", '''
from backend.plugins.base import BasePlugin, PluginManifest
class P(BasePlugin):
    manifest = PluginManifest(id="setupfail", name="SF", description="x")
    async def setup(self):
        raise ValueError("setup blew up")
''')
        reg = PluginRegistry()
        assert await loader.load_plugin(tmp_path / "setupfail", make_ctx(), reg) is None
        assert reg.get("setupfail") is None
        assert any("setup blew up" in (m.get("error") or "") for m in reg.manifests({}))

    async def test_no_plugin_class_is_an_error(self, tmp_path):
        write_plugin(tmp_path, "empty", "X = 1\n")
        reg = PluginRegistry()
        assert await loader.load_plugin(tmp_path / "empty", make_ctx(), reg) is None


class TestExamplePlugins:
    """The shipped example plugins must load cleanly through the public loader."""

    EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "plugins"

    @pytest.mark.parametrize(
        "plugin_id,hint,conflict",
        [("meshcore", "MeshCore", "meshtastic"), ("meshtastic", "Meshtastic", "meshcore")],
    )
    async def test_example_loads_with_manifest(self, plugin_id, hint, conflict):
        reg = PluginRegistry()
        inst = await loader.load_plugin(self.EXAMPLES / plugin_id, make_ctx(), reg)
        assert inst is not None, "example plugin failed to load"
        m = inst.manifest
        assert m.id == plugin_id
        assert conflict in m.conflicts_with
        assert m.tx_composition["hint"] == hint
        assert any(f.key == "serial_port" for f in m.config_schema)
    async def test_reload_picks_up_changes(self, tmp_path):
        d = write_plugin(tmp_path, "rel", GOOD.format(id="rel", ver="1"))
        reg = PluginRegistry()
        first = await loader.load_plugin(d, make_ctx(), reg)
        assert first.manifest.version == "1"
        (d / "plugin.py").write_text(GOOD.format(id="rel", ver="2"), encoding="utf-8")
        second = await loader.reload_plugin(d, make_ctx(), reg)
        assert second is not None and second is not first
        assert second.manifest.version == "2"
        assert reg.get("rel") is second  # old instance replaced

    async def test_unload_removes_and_purges_modules(self, tmp_path):
        write_plugin(tmp_path, "ul", GOOD.format(id="ul", ver="1"))
        reg = PluginRegistry()
        await loader.load_plugin(tmp_path / "ul", make_ctx(), reg)
        import sys
        assert "hw_plugin_ul" in sys.modules
        await loader.unload_plugin("ul", reg)
        assert reg.get("ul") is None
        assert "hw_plugin_ul" not in sys.modules  # modules purged for a clean reload
