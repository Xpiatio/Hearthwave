import threading
import time
import urllib.error
import urllib.request

PROBE_URL = "https://api.ke8rxnwx.net/crossref/"
PROBE_TIMEOUT_SECONDS = 2.5
PROBE_TTL_SECONDS = 60.0

_cache = {"value": None, "checked_at": 0.0}
_cache_lock = threading.Lock()


def _probe(url, timeout):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status is not None
    except urllib.error.HTTPError:
        return True


def is_online():
    with _cache_lock:
        now = time.monotonic()
        cached = _cache["value"]
        if cached is not None and (now - _cache["checked_at"]) < PROBE_TTL_SECONDS:
            return cached
        try:
            result = bool(_probe(PROBE_URL, PROBE_TIMEOUT_SECONDS))
        except (OSError, urllib.error.URLError, TimeoutError):
            result = False
        _cache["value"] = result
        _cache["checked_at"] = now
        return result


def invalidate():
    with _cache_lock:
        _cache["value"] = None
        _cache["checked_at"] = 0.0


def is_online_cached() -> bool | None:
    """Return the most-recently-cached online verdict without probing.

    Returns None when no probe has run yet. Use this when you need the
    online state instantly (e.g. on client connect) and can tolerate a
    brief period of unknowing at startup.
    """
    return _cache["value"]
