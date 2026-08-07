"""Shared machinery for plugins that receive station positions.

The inbound counterpart to ``mesh_forwarder.py``. Where a forwarder pushes
accepted TX out to a mesh, a position source pulls fixes in — from a mesh
radio's node database, an APRS TNC, or anything else that knows where other
stations are — and hands them to the core via ``ctx.report_position``.

This is a component, not a base class, deliberately. The Meshtastic plugin is
already a ``MeshForwarderPlugin``; a second base class would collide with it on
``_read_config`` and ``on_config_changed``. A plugin instead *owns* a poller and
drives it from its own lifecycle hooks:

    self._poller = PositionPoller("meshtastic", self._poll_nodes, ctx_getter=lambda: self.ctx)
    ...
    async def on_config_changed(self, config):
        await super().on_config_changed(config)
        await self._poller.configure(enabled=..., poll_seconds=...)

Polling rather than callbacks is deliberate too. Mesh libraries deliver events
on their own serial reader thread, which would need a
``loop.call_soon_threadsafe`` hop to reach the event loop safely; a node
database that already accumulates positions can just be read on a timer. A
genuinely push-based source (a socket) can still use this: block inside
``poll_once`` for as long as the link is up.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, NamedTuple

_log = logging.getLogger(__name__)

#: Floor on the poll interval. A plugin's config may ask for less; it doesn't
#: get it. Serial mesh reads are not free and nothing on a map moves this fast.
MIN_POLL_SECONDS = 5.0

#: Ignore an unchanged fix for the same node inside this window. Guards against
#: a digipeater echoing the same beacon three times in as many seconds.
DEFAULT_MIN_REPORT_INTERVAL_S = 10.0

#: Bound on the dedupe table so a busy band can't grow it without limit. Sized
#: above PositionStore.MAX_ENTRIES so it never evicts a node the store holds.
MAX_TRACKED_NODES = 1000


class _Seen(NamedTuple):
    """Last accepted fix for one node. ``heard_at`` is None for sources that
    don't timestamp — see :meth:`PositionPoller.report`."""

    at: float                    # monotonic, ours
    lat: float
    lon: float
    heard_at: float | None       # epoch, the source's


class PositionPoller:
    """Runs a plugin's position read on a timer and reports what it finds.

    Owns the task lifecycle, the poll interval floor, and per-node dedupe. The
    plugin supplies ``poll_once`` (and optionally ``on_start``/``on_stop`` to
    open and close a link) and calls :meth:`report` from inside it.
    """

    def __init__(
        self,
        source_name: str,
        poll_once: Callable[[], Awaitable[None]],
        *,
        ctx_getter: Callable[[], object],
        on_start: Callable[[], Awaitable[None]] | None = None,
        on_stop: Callable[[], Awaitable[None]] | None = None,
        min_report_interval_s: float = DEFAULT_MIN_REPORT_INTERVAL_S,
    ) -> None:
        self.source_name = source_name
        self.min_report_interval_s = min_report_interval_s
        self._poll_once = poll_once
        self._ctx_getter = ctx_getter
        self._on_start = on_start
        self._on_stop = on_stop
        self._poll_seconds = MIN_POLL_SECONDS
        self._task: asyncio.Task | None = None
        self._last_seen: dict[str, _Seen] = {}

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    # -- lifecycle -------------------------------------------------------
    async def configure(self, *, enabled: bool, poll_seconds: float) -> None:
        """Start, stop, or re-tune the poll loop. Safe to call on every config change."""
        self._poll_seconds = max(MIN_POLL_SECONDS, float(poll_seconds or 0))
        if enabled:
            self._start()
        else:
            await self.stop()

    def _start(self) -> None:
        if self.is_running:
            return  # interval is re-read each pass, so a running loop needs no restart
        self._task = asyncio.create_task(
            self._run_loop(), name=f"position-poller-{self.source_name}"
        )

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                _log.exception("%s: position poller stop failed", self.source_name)
        self._last_seen.clear()

    async def _run_loop(self) -> None:
        """Poll until cancelled. One bad poll never ends the loop.

        The interval is re-read each pass, so an admin changing it in Settings
        takes effect on the next tick without a reconnect.
        """
        if self._on_start is not None:
            try:
                await self._on_start()
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("%s: position source failed to open", self.source_name)
                return
        try:
            while True:
                try:
                    await self._poll_once()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _log.exception("%s: position poll failed", self.source_name)
                await asyncio.sleep(self._poll_seconds)
        except asyncio.CancelledError:
            pass
        finally:
            if self._on_stop is not None:
                try:
                    await self._on_stop()
                except Exception:
                    _log.exception("%s: position source teardown failed", self.source_name)

    # -- reporting -------------------------------------------------------
    async def report(
        self,
        node_id: str,
        lat: float,
        lon: float,
        label: str = "",
        **meta,
    ) -> bool:
        """Report one position, suppressing unchanged repeats.

        A node that has actually moved is always reported, however recently it
        was last heard. An unchanged fix is suppressed, but what counts as
        "unchanged" depends on the source:

        * A source that passes ``heard_at`` (a node database, which remembers
          nodes for days) is only telling us something new when that timestamp
          advances. Re-reading the same row every minute is not a new hearing,
          and treating it as one would keep a node that went off the air three
          days ago pinned to the map as if it were live.
        * A source that doesn't (a live APRS feed, where every packet *is* a
          hearing) gets the rate limit instead: same coordinates inside
          ``min_report_interval_s`` are dropped, so a digipeater echo doesn't
          count three times.
        """
        node_id = str(node_id or "").strip()
        if not node_id:
            return False
        now = asyncio.get_running_loop().time()
        heard_at = _as_epoch(meta.get("heard_at"))
        previous = self._last_seen.get(node_id)
        if previous is not None and previous.lat == lat and previous.lon == lon:
            if heard_at is not None and previous.heard_at is not None:
                if heard_at <= previous.heard_at:
                    return False
            elif (now - previous.at) < self.min_report_interval_s:
                return False

        ctx = self._ctx_getter()
        if ctx is None:
            return False
        reported = await ctx.report_position(  # type: ignore[attr-defined]
            self.source_name, node_id, lat, lon, label=label, **meta
        )
        if reported:
            self._remember(_Seen(now, lat, lon, heard_at), node_id)
        return bool(reported)

    def _remember(self, seen: _Seen, node_id: str) -> None:
        if node_id not in self._last_seen and len(self._last_seen) >= MAX_TRACKED_NODES:
            oldest = min(self._last_seen, key=lambda key: self._last_seen[key].at)
            del self._last_seen[oldest]
        self._last_seen[node_id] = seen


def _as_epoch(raw: object) -> float | None:
    """Coerce a source-supplied heard timestamp, or None if it isn't one."""
    if raw is None:
        return None
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
