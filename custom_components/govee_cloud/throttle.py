"""Per-device pacing and coalescing for Govee control commands.

Govee allows 2 control requests per second per device. Dragging a color
wheel or brightness slider in HA fires many commands in a row, so:

* commands to one device are sent one at a time, at most one every
  MIN_INTERVAL seconds, and
* while a command is waiting, a newer value for the same setting replaces
  it, so only the latest color or brightness is sent.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import time
from typing import Any

MIN_INTERVAL = 0.6

Sender = Callable[[str, str, Any], Awaitable[None]]


class CommandThrottle:
    """Serialize, pace and coalesce commands for one device."""

    def __init__(self, sender: Sender, min_interval: float | None = None) -> None:
        """Initialize the throttle."""
        self._sender = sender
        self._min_interval = MIN_INTERVAL if min_interval is None else min_interval
        self._lock = asyncio.Lock()
        self._pending: dict[str, tuple[str, Any]] = {}
        self._last_sent = 0.0

    async def send(self, cap_type: str, instance: str, value: Any) -> Any:
        """Queue a command; a newer value for the same setting replaces it.

        Returns the value actually sent, or None if another caller sent it.
        """
        self._pending[instance] = (cap_type, value)
        async with self._lock:
            if instance not in self._pending:
                # An earlier caller already sent a newer value for this setting.
                return None
            cap_type, value = self._pending.pop(instance)
            wait = self._last_sent + self._min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                await self._sender(cap_type, instance, value)
            finally:
                self._last_sent = time.monotonic()
            return value
