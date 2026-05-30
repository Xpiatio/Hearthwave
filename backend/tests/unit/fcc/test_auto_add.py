"""``CallsignLookupWorker`` is a thin asyncio wrapper around
``verify_callsign``. The point of these tests is to lock in the contract the
caller relies on:

* ``start()`` schedules a task that invokes ``verify_callsign`` with the
  worker's callsign + name.
* ``on_result`` receives the original callsign / transcript-derived name +
  location plus the ``VerificationResult`` so the receiver doesn't have to
  maintain per-lookup state.
* The class can be instantiated and driven without a live HTTP stack.
"""
import asyncio
from unittest.mock import patch

import pytest

from backend.fcc import auto_add
from backend.fcc.crossref import VerificationResult


class TestCallsignLookupWorker:
    @pytest.mark.asyncio
    async def test_run_invokes_verify_with_callsign_and_name(self):
        fake = VerificationResult(status="verified", license_name="Zomberg, Benjamin J")
        received = []

        async def on_result(cs, n, loc, r):
            received.append((cs, n, loc, r))

        worker = auto_add.CallsignLookupWorker("WSLZ233", "Benjamin", "Jenison", on_result)
        with patch.object(auto_add, "verify_callsign", return_value=fake) as vc:
            await worker.start()
        vc.assert_called_once_with("WSLZ233", "Benjamin")
        assert received == [("WSLZ233", "Benjamin", "Jenison", fake)]

    @pytest.mark.asyncio
    async def test_result_callback_carries_original_transcript_metadata(self):
        """The receiver builds the contact dict from these fields, so they
        must survive even when the lookup result has its own license_name."""
        fake = VerificationResult(
            status="verified",
            license_name="Hoekema, Collin J",
            license_city="GRAND RAPIDS",
        )
        captured = []

        async def on_result(cs, n, loc, r):
            captured.append((cs, n, loc, r.license_name))

        worker = auto_add.CallsignLookupWorker("KE8RXN", "Collin", "Grand Rapids", on_result)
        with patch.object(auto_add, "verify_callsign", return_value=fake):
            await worker.start()
        assert captured == [("KE8RXN", "Collin", "Grand Rapids", "Hoekema, Collin J")]
