# Writing Hearthwave plugins

Hearthwave has an installable plugin system. A plugin is a small Python package you
drop into the server's plugins directory (or upload through the admin UI); it hooks
into the message/audio pipeline and exposes its settings declaratively, which the
app renders into a form automatically. **Plugins ship no browser code.**

The bundled **MeshCore** and **Meshtastic** bridges under `examples/plugins/` are
real, working plugins — read them alongside this guide.

> ⚠️ **Trust model.** Plugins run in the server process with full privileges (like
> Home Assistant custom components). There is no sandbox. Only install plugins you
> trust. Installing/managing plugins is admin-only.

---

## Where plugins live & how they load

```
<data>/plugins/
  meshcore/
    plugin.py
  my_plugin/
    plugin.py
    helpers.py        # optional; import with `from . import helpers`
```

- The plugins directory defaults to `/data/plugins` (override with
  `RADIO_TTY_PLUGINS_DIR`). It's a persisted volume.
- Each **sub-directory containing a `plugin.py`** is one plugin. The **directory
  name is the plugin id** (used for config namespacing + install/uninstall).
- Plugins load at server startup. They also **hot-reload** at runtime:
  - **Install** — Settings → **Plugins** → *Install plugin (.zip)*, or drop a folder
    into the plugins dir and hit **Reload**.
  - **Reload / Uninstall** — per-plugin buttons in the Plugins page.
  - A server restart always reloads everything cleanly as a fallback.
- A plugin that fails to import or set up does **not** crash the server — its error
  is shown in the Plugins page.

### Packaging for upload
Zip the plugin so the archive contains `<id>/plugin.py` (a top-level folder), e.g.

```bash
cd my_plugin && zip -r ../my_plugin.zip . && cd ..   # → my_plugin.zip with my_plugin/plugin.py
```

Then upload it from the Plugins page.

---

## The SDK

Import everything from `backend.plugins.sdk` (the stable surface):

```python
from backend.plugins.sdk import (
    BasePlugin, PluginManifest, ConfigField, PluginContext,
    MeshForwarderPlugin, MeshTransport, MeshForwardConfig,  # reusable mesh-bridge base
)
```

### Exposing your plugin
`plugin.py` must provide one of (checked in this order):
1. a module-level `PLUGIN` that is a `BasePlugin` instance,
2. a module-level `get_plugin()` factory returning one, or
3. a single `BasePlugin` subclass defined in the module (instantiated with no args).

### `BasePlugin` — lifecycle & hooks
All hooks are optional no-ops; override what you need.

| Hook | When |
|------|------|
| `async setup()` | once after construction, before registration (cheap init) |
| `async on_config_changed(config)` | at startup and after every settings save — open/close connections here |
| `async on_unload()` | on reload/uninstall/shutdown — cancel tasks, close links |
| `async on_client_message_received(payload, reply=None)` | every inbound WebSocket message |
| `async on_audio_rx_start()` | squelch opens (incoming transmission) |
| `on_audio_rx_chunk(chunk)` | each raw audio chunk (**sync, hot path** — be fast) |
| `async on_rx_final(text)` | each finalized receive transcript |
| `async on_audio_tx_pre_queue(payload) -> dict \| None` | before a transmission is synthesized; return the payload to allow, `None` to block |

Active hooks fire only while your plugin is **enabled**. `on_config_changed` is the
exception — it **always** fires, even when you're disabled, so you can tear down on
the transition. So if you hold a resource (a connection, a background task), open or
close it in `on_config_changed` based on your own enabled flag, and also release it
in `on_unload`:

```python
async def on_config_changed(self, config):
    if config.plugin_enabled("my_plugin"):
        await self._connect(config.plugin_config("my_plugin"))
    else:
        await self._teardown()
```

**Reading your settings:** `on_config_changed(config)` receives the live config;
elsewhere use `self.ctx.get_config()`. Your section is `config.plugin_config("<id>")`
(a dict of your `config_schema` values) and your master toggle is
`config.plugin_enabled("<id>")`.

**Intercepting transmissions** (`on_audio_tx_pre_queue`): return the `payload`
(optionally modified) to allow the transmit, or `None` to block it. Plugins run in
registration order and the **first to return `None` wins**. The fields you may
modify are `text`, `_filter_profanity`, `_voice_name`, and `_length_scale`. This
hook must never block the radio — keep it fast and best-effort (the mesh examples
enqueue onto their own queue and return immediately).

### `PluginContext` — `self.ctx`
Bound before `setup()`. Your only door to core services:

| Member | Use |
|--------|-----|
| `await ctx.broadcast(msg)` | send a JSON dict to all connected clients |
| `await ctx.enqueue_tx(payload)` | queue a transmission, e.g. `{"text": "...", "_pre_formatted": True}` |
| `ctx.get_config()` | the live config; your settings are at `ctx.get_config().plugin_config(id)` |
| `ctx.channel_clear()` | `True` when the channel is idle (safe to transmit) |
| `ctx.data_dir` | the writable data directory (for plugin state files) |
| `ctx.logger` | a logger namespaced to your plugin |

### `PluginManifest`
```python
PluginManifest(
    id="my_plugin",                  # should match the directory name
    name="My Plugin",
    description="One line shown in the Plugins page.",
    version="1.0.0",
    default_enabled=False,           # on/off when first installed
    conflicts_with=("other_id",),    # enabling this disables those (mutual exclusion)
    config_schema=(...),             # ConfigFields — rendered into a settings form
    tx_composition=None,             # optional mesh-bridge capability (see below)
)
```

### `ConfigField` — declarative settings
Each field is rendered into the Plugins-page form and stored under your namespace.

```python
ConfigField("serial_port", "Device", "text", "/dev/ttyUSB0", help="Serial device")
ConfigField("baud", "Baud rate", "number", 115200, minimum=1)
ConfigField("mode", "Mode", "select", "a", options=(("a", "Mode A"), ("b", "Mode B")))
ConfigField("loud", "Be loud", "bool", False)
```
Types: `text` | `number` | `bool` | `select`. Numbers are clamped to
`minimum`/`maximum`; selects to their `options`; unknown keys are rejected.

### Config namespacing
Your settings live under `config["plugins"][<id>]`: the master toggle at
`"enabled"`, plus one key per `ConfigField`. Read them with:

```python
cfg = self.ctx.get_config().plugin_config("my_plugin")
port = cfg.get("serial_port", "/dev/ttyUSB0")   # fall back to the field default
```

### `tx_composition` (mesh-bridge capability)
If your plugin prefixes and forwards transmissions like a mesh bridge, declare this
so the message input reserves room for the prefix automatically:

```python
tx_composition={"max_len_key": "max_packet_length", "separator_key": "prefix_separator", "hint": "MyMesh"}
```
The keys reference fields in your own `config_schema`.

### Dependencies
Bundling pip dependencies isn't automatic. **Import optional libraries lazily**
inside the method that needs them and raise a clear error if absent (see the mesh
examples) — that way your plugin still loads and lists, and the failure is obvious
only when actually used. Required libraries must be present in the server image.

---

## Hello world

`<data>/plugins/hello/plugin.py`:

```python
from backend.plugins.sdk import BasePlugin, PluginManifest, ConfigField


class HelloPlugin(BasePlugin):
    manifest = PluginManifest(
        id="hello",
        name="Hello World",
        description="Logs each finished transmission, optionally shouting it back.",
        config_schema=(
            ConfigField("shout", "Echo to all clients", "bool", False),
            ConfigField("prefix", "Log prefix", "text", "heard"),
        ),
    )

    async def on_rx_final(self, text: str) -> None:
        cfg = self.ctx.get_config().plugin_config("hello")
        self.ctx.logger.info("%s: %s", cfg.get("prefix", "heard"), text)
        if cfg.get("shout"):
            await self.ctx.broadcast({"type": "chat", "text": f"(hello) {text}"})
```

Install it (drop the folder in, or zip + upload), enable it in **Settings →
Plugins**, and toggle "Echo to all clients" — no rebuild, no restart.

---

## Reference examples
- `examples/plugins/meshcore/plugin.py` — serial transport + `MeshForwarderPlugin` +
  `tx_composition` + a full `config_schema`.
- `examples/plugins/meshtastic/plugin.py` — same shape, wrapping a blocking library
  in a thread executor; mutually exclusive with MeshCore via `conflicts_with`.
