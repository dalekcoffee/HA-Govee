"""Config flow for Govee Cloud."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoveeApi, GoveeApiError, GoveeAuthError, GoveeDevice
from .const import CONF_DEVICES, DOMAIN


async def _fetch_lights(
    flow: ConfigFlow | OptionsFlow, api_key: str
) -> list[GoveeDevice]:
    api = GoveeApi(async_get_clientsession(flow.hass), api_key)
    return [d for d in await api.get_devices() if d.is_light]


def _device_choices(lights: list[GoveeDevice]) -> dict[str, str]:
    return {d.device_id: f"{d.name} ({d.sku})" for d in lights}


class GoveeCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee Cloud."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._api_key: str | None = None
        self._lights: list[GoveeDevice] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            try:
                self._lights = await _fetch_lights(self, api_key)
            except GoveeAuthError:
                errors["base"] = "invalid_auth"
            except GoveeApiError:
                errors["base"] = "cannot_connect"
            else:
                if not self._lights:
                    return self.async_abort(reason="no_lights")
                self._api_key = api_key
                return await self.async_step_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which lights to add."""
        choices = _device_choices(self._lights)
        if user_input is not None:
            return self.async_create_entry(
                title="Govee Cloud",
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_DEVICES: user_input[CONF_DEVICES],
                },
            )
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES, default=list(choices)): cv.multi_select(
                        choices
                    )
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when Govee rejects the stored key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            entry = self._get_reauth_entry()
            try:
                lights = await _fetch_lights(self, api_key)
            except GoveeAuthError:
                errors["base"] = "invalid_auth"
            except GoveeApiError:
                errors["base"] = "cannot_connect"
            else:
                selected = set(
                    entry.options.get(CONF_DEVICES, entry.data.get(CONF_DEVICES, []))
                )
                if selected and not selected & {d.device_id for d in lights}:
                    errors["base"] = "wrong_account"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_API_KEY: api_key}
                    )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> GoveeCloudOptionsFlow:
        """Return the options flow."""
        return GoveeCloudOptionsFlow()


class GoveeCloudOptionsFlow(OptionsFlow):
    """Change which lights are added."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick lights again."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        try:
            lights = await _fetch_lights(self, self.config_entry.data[CONF_API_KEY])
        except GoveeApiError:
            return self.async_abort(reason="cannot_connect")

        choices = _device_choices(lights)
        current = self.config_entry.options.get(
            CONF_DEVICES, self.config_entry.data.get(CONF_DEVICES, [])
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICES, default=[d for d in current if d in choices]
                    ): cv.multi_select(choices)
                }
            ),
        )
