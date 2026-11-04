"""The Govee Cloud integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoveeApi, GoveeApiError, GoveeAuthError
from .const import CONF_DEVICES
from .coordinator import GoveeConfigEntry, GoveeCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: GoveeConfigEntry) -> bool:
    """Set up Govee Cloud from a config entry."""
    api = GoveeApi(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    try:
        devices = await api.get_devices()
    except GoveeAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except GoveeApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    selected = set(entry.options.get(CONF_DEVICES, entry.data.get(CONF_DEVICES, [])))
    lights = [d for d in devices if d.is_light and d.device_id in selected]

    coordinator = GoveeCoordinator(hass, entry, api, lights)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: GoveeConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
