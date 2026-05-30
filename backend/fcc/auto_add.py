"""Background FCC lookup used to auto-add unknown stations to contacts.

When the STT pipeline surfaces a callsign that isn't in the contact list AND
the transcript carried a plausible operator name, we'd like to ask the FCC
crossref API whether that name actually matches the licensee. A name match
means we can drop the contact straight into ``contacts.json`` with full GMRS
+ HAM cross-references; a mismatch (or any other non-``verified`` status)
leaves the pending '+ Add' pill in place so the operator can decide.

The lookup must not block the event loop — ``verify_callsign`` can sit on a
five-second HTTP timeout. ``CallsignLookupWorker`` offloads the call to a
thread pool via ``asyncio.to_thread`` and delivers the result by invoking an
async callback passed in at construction time.
"""
import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from backend.fcc.crossref import VerificationResult, verify_callsign


class CallsignLookupWorker:
    """Runs one ``verify_callsign`` call on a background thread via asyncio.

    The transcript-derived ``name`` and ``location`` are passed through verbatim
    to ``on_result`` so the receiver can build the contact dict without
    holding extra state per in-flight lookup.

    ``on_result`` is an async callable with the signature::

        async def on_result(
            callsign: str,
            name: str,
            location: str,
            result: VerificationResult,
        ) -> None: ...

    Call ``start()`` to schedule the lookup as an asyncio task.
    """

    def __init__(
        self,
        callsign: str,
        name: str,
        location: str,
        on_result: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        self.callsign = callsign
        self.name = name
        self.location = location
        self._on_result = on_result

    async def _run(self) -> None:
        result = await asyncio.to_thread(verify_callsign, self.callsign, self.name)
        await self._on_result(self.callsign, self.name, self.location, result)

    def start(self) -> asyncio.Task:
        return asyncio.create_task(self._run())
