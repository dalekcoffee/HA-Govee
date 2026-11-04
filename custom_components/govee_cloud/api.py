"""Minimal client for the official Govee Developer Platform API.

Only talks to https://openapi.api.govee.com using the API key the user
requested in the Govee Home app. Docs: https://developer.govee.com/
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Any
import uuid

import aiohttp

from .const import API_BASE_URL, CAP_ON_OFF, INST_POWER, TYPE_LIGHT

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

# Govee allows about 12 control commands per second for a whole account, on
# top of the per-device limit. Setting every light at once easily goes over
# that, so commands from all lights share one pace, kept under the limit.
# Read at runtime so tests can turn it off.
ACCOUNT_MIN_INTERVAL = 0.125


class GoveeApiError(Exception):
    """Generic error talking to the Govee API."""


class GoveeAuthError(GoveeApiError):
    """The API key was rejected."""


class GoveeRateLimitError(GoveeApiError):
    """Govee returned HTTP 429."""


@dataclass
class GoveeDevice:
    """A device returned by the Govee device list."""

    sku: str
    device_id: str
    name: str
    device_type: str | None
    # (capability type, instance) -> parameters
    capabilities: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def has(self, instance: str) -> bool:
        """Return True if the device has a capability with this instance."""
        return any(inst == instance for _, inst in self.capabilities)

    def parameters(self, instance: str) -> dict[str, Any]:
        """Return the parameters for a capability instance."""
        for (_, inst), params in self.capabilities.items():
            if inst == instance:
                return params
        return {}

    @property
    def is_group(self) -> bool:
        """Return True for a group of devices made in the Govee app."""
        return self.sku.endswith("Group") or self.device_type is None

    @property
    def is_light(self) -> bool:
        """Return True if this device can be controlled as a light.

        Groups made in the Govee app (sku "SameModeGroup", no type) are left
        out: their state can't be read, and powering a group while its bulbs
        are being set individually turns those bulbs off again.
        """
        if self.is_group or self.device_type != TYPE_LIGHT:
            return False
        return (CAP_ON_OFF, INST_POWER) in self.capabilities


class GoveeApi:
    """Async client for the Govee Developer Platform API."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key
        self._control_lock = asyncio.Lock()
        self._next_control = 0.0

    async def _wait_for_control_slot(self) -> None:
        async with self._control_lock:
            delay = self._next_control - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_control = time.monotonic() + ACCOUNT_MIN_INTERVAL

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {
            "Govee-API-Key": self._api_key,
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise GoveeAuthError("Govee rejected the API key")
                if resp.status == 429:
                    raise GoveeRateLimitError("Govee rate limit reached")
                try:
                    body = await resp.json(content_type=None)
                except ValueError as err:
                    raise GoveeApiError(
                        f"Invalid response from Govee (HTTP {resp.status})"
                    ) from err
                if resp.status != 200:
                    raise GoveeApiError(
                        f"Govee returned HTTP {resp.status}: {_message(body)}"
                    )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise GoveeApiError(f"Error talking to Govee: {err}") from err

        if not isinstance(body, dict):
            raise GoveeApiError("Unexpected response from Govee")
        code = body.get("code", 200)
        if code == 401:
            raise GoveeAuthError("Govee rejected the API key")
        if code == 429:
            raise GoveeRateLimitError("Govee rate limit reached")
        if code != 200:
            raise GoveeApiError(f"Govee returned code {code}: {_message(body)}")
        return body

    async def get_devices(self) -> list[GoveeDevice]:
        """Return all devices on the account."""
        body = await self._request("GET", "/router/api/v1/user/devices")
        devices: list[GoveeDevice] = []
        for raw in body.get("data") or []:
            sku = raw.get("sku")
            device_id = raw.get("device")
            if not sku or not device_id:
                continue
            caps = {
                (cap["type"], cap["instance"]): cap.get("parameters") or {}
                for cap in raw.get("capabilities") or []
                if "type" in cap and "instance" in cap
            }
            devices.append(
                GoveeDevice(
                    sku=sku,
                    device_id=device_id,
                    name=raw.get("deviceName") or f"Govee {sku}",
                    device_type=raw.get("type"),
                    capabilities=caps,
                )
            )
        return devices

    async def get_state(self, device: GoveeDevice) -> dict[str, Any]:
        """Return the current state as {instance: value}."""
        body = await self._request(
            "POST",
            "/router/api/v1/device/state",
            {
                "requestId": str(uuid.uuid4()),
                "payload": {"sku": device.sku, "device": device.device_id},
            },
        )
        payload = body.get("payload") or {}
        state: dict[str, Any] = {}
        for cap in payload.get("capabilities") or []:
            instance = cap.get("instance")
            value = (cap.get("state") or {}).get("value")
            # An empty string means the device does not support querying it.
            if instance and value != "":
                state[instance] = value
        return state

    async def control(
        self, device: GoveeDevice, cap_type: str, instance: str, value: Any
    ) -> None:
        """Send one control command."""
        await self._wait_for_control_slot()
        await self._request(
            "POST",
            "/router/api/v1/device/control",
            {
                "requestId": str(uuid.uuid4()),
                "payload": {
                    "sku": device.sku,
                    "device": device.device_id,
                    "capability": {
                        "type": cap_type,
                        "instance": instance,
                        "value": value,
                    },
                },
            },
        )


def _message(body: Any) -> str:
    if isinstance(body, dict):
        return str(body.get("msg") or body.get("message") or "")
    return ""
