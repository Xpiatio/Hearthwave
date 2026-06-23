"""Endpoint tests for the admin plugin install / reload / uninstall routes.

These drive the real FastAPI app via TestClient (no lifespan — module globals are
seeded manually, mirroring test_auth_routes' style) so the route wiring, zip
handling, and loader integration are exercised end-to-end.
"""
from __future__ import annotations

import io
import logging
import sys
import zipfile
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

# backend.server transitively imports audio/ML deps at load time; stub them so
# tests run without audio hardware (mirrors test_server_beacon).
for _stub in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_stub, MagicMock())
_piper_config_stub = MagicMock()
_piper_config_stub.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config_stub)

import backend.server as srv
from backend.config import ServerConfig
from backend.plugins.context import PluginContext
from backend.plugins.registry import plugin_registry

HELLO = (
    "from backend.plugins.base import BasePlugin, PluginManifest\n"
    "class Hello(BasePlugin):\n"
    "    manifest = PluginManifest(id='hello', name='Hello', description='hi')\n"
)


def _zip(arcname_to_body: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in arcname_to_body.items():
            z.writestr(name, body)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Fresh registry + manually-seeded globals (no lifespan).
    plugin_registry._plugins = ()
    plugin_registry._load_errors = {}
    srv._config = ServerConfig()
    srv._PLUGINS_DIR = tmp_path

    async def _noop(*_a, **_k):
        return None

    srv._plugin_ctx = PluginContext(
        broadcast=_noop, enqueue_tx=_noop, get_config=lambda: srv._config,
        channel_clear=lambda: True, data_dir=tmp_path, logger=logging.getLogger("t"),
    )
    monkeypatch.setattr(srv, "_build_status", lambda: {"type": "status"})
    monkeypatch.setattr(srv._manager, "broadcast", _noop)
    return TestClient(srv.app, raise_server_exceptions=False)


def _as_admin(monkeypatch):
    monkeypatch.setattr(srv.auth_routes, "_require_admin", lambda authorization: "admin")


class TestInstall:
    def test_requires_admin(self, client):
        # No auth header → _require_admin raises 401 (no token store configured).
        r = client.post("/plugins/install", files={"file": ("p.zip", b"x", "application/zip")})
        assert r.status_code in (401, 403)

    def test_install_loads_plugin_live(self, client, tmp_path, monkeypatch):
        _as_admin(monkeypatch)
        data = _zip({"hello/plugin.py": HELLO})
        r = client.post("/plugins/install", files={"file": ("hello.zip", data, "application/zip")})
        assert r.status_code == 200, r.text
        assert (tmp_path / "hello" / "plugin.py").is_file()
        assert plugin_registry.get("hello") is not None

    def test_rejects_non_zip(self, client, monkeypatch):
        _as_admin(monkeypatch)
        r = client.post("/plugins/install", files={"file": ("x.zip", b"not a zip", "application/zip")})
        assert r.status_code == 400

    def test_rejects_archive_without_plugin_py(self, client, monkeypatch):
        _as_admin(monkeypatch)
        data = _zip({"hello/readme.txt": "hi"})
        r = client.post("/plugins/install", files={"file": ("hello.zip", data, "application/zip")})
        assert r.status_code == 400

    def test_rejects_zip_slip(self, client, monkeypatch):
        _as_admin(monkeypatch)
        data = _zip({"../evil/plugin.py": HELLO})
        r = client.post("/plugins/install", files={"file": ("evil.zip", data, "application/zip")})
        assert r.status_code == 400

    def test_broken_plugin_reports_load_error(self, client, monkeypatch):
        _as_admin(monkeypatch)
        data = _zip({"boom/plugin.py": "raise RuntimeError('nope')\n"})
        r = client.post("/plugins/install", files={"file": ("boom.zip", data, "application/zip")})
        assert r.status_code == 400
        assert "failed to load" in r.json()["detail"].lower()


class TestReloadUninstall:
    def test_reload_missing_is_404(self, client, monkeypatch):
        _as_admin(monkeypatch)
        assert client.post("/plugins/ghost/reload").status_code == 404

    def test_uninstall_removes_plugin(self, client, tmp_path, monkeypatch):
        _as_admin(monkeypatch)
        client.post("/plugins/install", files={"file": ("hello.zip", _zip({"hello/plugin.py": HELLO}), "application/zip")})
        assert plugin_registry.get("hello") is not None
        r = client.delete("/plugins/hello")
        assert r.status_code == 200
        assert plugin_registry.get("hello") is None
        assert not (tmp_path / "hello").exists()
