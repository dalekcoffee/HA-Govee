"""Polling coordinator for Govee Cloud."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GoveeApi,
    GoveeApiError,
    GoveeAuthError,
    GoveeDevice,
    GoveeRateLimitError,
)
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GoveeConfigEntry = ConfigEntry[GoveeCoordinator]


class GoveeCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch the state of every selected device once per interval."""

    config_entry: GoveeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GoveeConfigEntry,
        api: GoveeApi,
        devices: list[GoveeDevice],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.devices = {device.device_id: device for device in devices}
        self.options_snapshot: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        data: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        for device_id, device in self.devices.items():
            try:
                data[device_id] = await self.api.get_state(device)
            except GoveeAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except GoveeRateLimitError as err:
                # Stop polling the remaining devices so we don't use up
                # more of the account's quota.
                raise UpdateFailed(str(err)) from err
            except GoveeApiError as err:
                errors.append(f"{device.name}: {err}")
                # Leave this device out; its entity shows unavailable until
                # a poll succeeds again.
        if errors and not data:
            raise UpdateFailed("; ".join(errors))
        for error in errors:
            _LOGGER.debug("Could not update %s", error)
        return data

    def apply_local_state(self, device_id: str, values: dict[str, Any]) -> None:
        """Store values we just sent so the UI updates before the next poll."""
        # Skip devices whose last poll failed so they stay unavailable.
        if self.data is None or device_id not in self.data:
            return
        self.data[device_id].update(values)
        self.async_update_listeners()
