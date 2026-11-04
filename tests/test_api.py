"""Govee API client tests."""

import asyncio
import itertools
import time

from custom_components.govee_cloud import api as api_mod
from custom_components.govee_cloud.api import GoveeApi, GoveeDevice


async def test_controls_share_account_pace(monkeypatch):
    """Commands for different lights are spaced to stay under the account limit."""
    monkeypatch.setattr(api_mod, "ACCOUNT_MIN_INTERVAL", 0.05)
    api = GoveeApi(None, "key")
    sent: list[float] = []

    async def fake_request(*_args, **_kwargs):
        sent.append(time.monotonic())
        return {}

    monkeypatch.setattr(api, "_request", fake_request)
    devices = [GoveeDevice("H6008", f"id{i}", f"Bulb {i}", None) for i in range(4)]
    await asyncio.gather(*(api.control(d, "on_off", "powerSwitch", 1) for d in devices))
    gaps = [b - a for a, b in itertools.pairwise(sent)]
    assert len(sent) == 4
    assert all(gap >= 0.045 for gap in gaps)
