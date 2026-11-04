"""Throttle tests."""

import asyncio
import time

from custom_components.govee_cloud.throttle import CommandThrottle


async def test_coalesces_rapid_updates():
    sent = []
    gate = asyncio.Event()

    async def sender(cap_type, instance, value):
        sent.append((instance, value))
        if len(sent) == 1:
            await gate.wait()

    throttle = CommandThrottle(sender, min_interval=0)
    first = asyncio.create_task(throttle.send("color", "colorRgb", 1))
    await asyncio.sleep(0)
    # While the first command is in flight, three more arrive.
    rest = [
        asyncio.create_task(throttle.send("color", "colorRgb", v)) for v in (2, 3, 4)
    ]
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(first, *rest)
    # Only the first and the latest value were sent.
    assert sent == [("colorRgb", 1), ("colorRgb", 4)]


async def test_paces_commands():
    stamps = []

    async def sender(cap_type, instance, value):
        stamps.append(time.monotonic())

    throttle = CommandThrottle(sender, min_interval=0.2)
    await throttle.send("on_off", "powerSwitch", 1)
    await throttle.send("range", "brightness", 50)
    assert stamps[1] - stamps[0] >= 0.19
