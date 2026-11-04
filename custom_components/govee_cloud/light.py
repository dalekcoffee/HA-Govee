"""Light platform for Govee Cloud."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .api import GoveeApiError, GoveeDevice, GoveeRateLimitError
from .const import (
    CAP_COLOR,
    CAP_ON_OFF,
    CAP_RANGE,
    DOMAIN,
    INST_BRIGHTNESS,
    INST_COLOR_TEMP,
    INST_ONLINE,
    INST_POWER,
    INST_RGB,
)
from .colors import adapt_rgb
from .coordinator import GoveeConfigEntry, GoveeCoordinator
from .throttle import CommandThrottle

_LOGGER = logging.getLogger(__name__)

# Each light paces its own commands (see throttle.py), so HA does not need
# to serialize service calls; serializing would also stop coalescing.
PARALLEL_UPDATES = 0

# Wait this long before retrying a command Govee rate-limited.
RATE_LIMIT_RETRY_DELAY = 1.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoveeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Govee lights from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        GoveeLight(coordinator, device) for device in coordinator.devices.values()
    )


def _range(
    device: GoveeDevice, instance: str, default: tuple[int, int]
) -> tuple[int, int]:
    rng = device.parameters(instance).get("range") or {}
    try:
        return int(rng["min"]), int(rng["max"])
    except (KeyError, TypeError, ValueError):
        return default


class GoveeLight(CoordinatorEntity[GoveeCoordinator], LightEntity):
    """A Govee light controlled through the Govee cloud API."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: GoveeCoordinator, device: GoveeDevice) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = device.device_id
        self._throttle = CommandThrottle(self._control)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="Govee",
            model=device.sku,
            name=device.name,
        )
        self._brightness_range = _range(device, INST_BRIGHTNESS, (1, 100))
        kelvin_min, kelvin_max = _range(device, INST_COLOR_TEMP, (2000, 9000))
        self._attr_min_color_temp_kelvin = kelvin_min
        self._attr_max_color_temp_kelvin = kelvin_max

        modes: set[ColorMode] = set()
        if device.has(INST_RGB):
            modes.add(ColorMode.RGB)
        if device.has(INST_COLOR_TEMP):
            modes.add(ColorMode.COLOR_TEMP)
        if not modes:
            modes.add(
                ColorMode.BRIGHTNESS if device.has(INST_BRIGHTNESS) else ColorMode.ONOFF
            )
        self._attr_supported_color_modes = modes

    @property
    def _state(self) -> dict[str, Any] | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._device.device_id)

    @property
    def available(self) -> bool:
        """Unavailable if the last poll failed or Govee says it is offline."""
        state = self._state
        if not super().available or state is None:
            return False
        return state.get(INST_ONLINE) is not False

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        state = self._state
        if state is None or INST_POWER not in state:
            return None
        return state[INST_POWER] == 1

    @property
    def brightness(self) -> int | None:
        """Return brightness on HA's 0-255 scale."""
        state = self._state
        if state is None:
            return None
        value = state.get(INST_BRIGHTNESS)
        if not isinstance(value, (int, float)) or value <= 0:
            return None
        return value_to_brightness(self._brightness_range, value)

    @property
    def color_mode(self) -> ColorMode:
        """Return the active color mode."""
        modes = self._attr_supported_color_modes or set()
        if len(modes) == 1:
            return next(iter(modes))
        state = self._state or {}
        kelvin = state.get(INST_COLOR_TEMP)
        # Govee reports colorTemperatureK as 0 while the bulb is in RGB mode.
        if isinstance(kelvin, (int, float)) and kelvin > 0:
            return ColorMode.COLOR_TEMP
        return ColorMode.RGB

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color."""
        value = (self._state or {}).get(INST_RGB)
        if not isinstance(value, int):
            return None
        return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        value = (self._state or {}).get(INST_COLOR_TEMP)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
        return None

    async def _control(self, cap_type: str, instance: str, value: Any) -> None:
        try:
            await self.coordinator.api.control(self._device, cap_type, instance, value)
        except GoveeRateLimitError:
            # Back off once; Govee's limit is a short burst window.
            await asyncio.sleep(RATE_LIMIT_RETRY_DELAY)
            await self.coordinator.api.control(self._device, cap_type, instance, value)

    async def _send(self, cap_type: str, instance: str, value: Any) -> Any:
        """Send a command. Returns the value sent, or None if coalesced."""
        try:
            return await self._throttle.send(cap_type, instance, value)
        except GoveeApiError as err:
            _LOGGER.warning(
                "Govee rejected %s=%s for %s (%s): %s",
                instance,
                value,
                self._device.name,
                self._device.sku,
                err,
            )
            raise HomeAssistantError(
                f"Could not control {self._device.name}: {err}"
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally setting color or brightness."""
        commands: list[tuple[str, str, Any]] = []

        # A plain "turn on" always sends power, since the cached state can be
        # up to a minute old. When only changing color or brightness on a
        # light we believe is on, skip it to halve the requests.
        changes = {
            ATTR_RGB_COLOR,
            ATTR_COLOR_TEMP_KELVIN,
            ATTR_BRIGHTNESS,
        } & kwargs.keys()
        if not changes or not self.is_on:
            commands.append((CAP_ON_OFF, INST_POWER, 1))
        shown: dict[str, Any] = {INST_POWER: 1}

        color_brightness: int | None = None
        if ATTR_RGB_COLOR in kwargs:
            # Dark colours (like brown) become a full-intensity hue plus a
            # lower brightness, which is how they actually look on a bulb.
            (red, green, blue), color_brightness = adapt_rgb(
                tuple(kwargs[ATTR_RGB_COLOR])
            )
            value = (red << 16) | (green << 8) | blue
            commands.append((CAP_COLOR, INST_RGB, value))
            shown[INST_RGB] = value
            shown[INST_COLOR_TEMP] = 0
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            low = self._attr_min_color_temp_kelvin
            high = self._attr_max_color_temp_kelvin
            kelvin = max(low, min(high, int(kwargs[ATTR_COLOR_TEMP_KELVIN])))
            commands.append((CAP_COLOR, INST_COLOR_TEMP, kelvin))
            shown[INST_COLOR_TEMP] = kelvin

        level: float | None = None
        if ATTR_BRIGHTNESS in kwargs:
            level = brightness_to_value(self._brightness_range, kwargs[ATTR_BRIGHTNESS])
        elif color_brightness is not None:
            # Brightness implied by a dark colour, as a 0-100 percentage.
            low, high = self._brightness_range
            level = low + (high - low) * (color_brightness - 1) / 99
        if level is not None and self._device.has(INST_BRIGHTNESS):
            low, high = self._brightness_range
            value = max(low, min(high, round(level)))
            commands.append((CAP_RANGE, INST_BRIGHTNESS, value))
            shown[INST_BRIGHTNESS] = value

        # Show the requested values right away, in request order, so the
        # newest request always wins in the UI even if commands to the bulb
        # finish out of order or are merged.
        self.coordinator.apply_local_state(self._device.device_id, shown)
        for cap_type, instance, value in commands:
            await self._send(cap_type, instance, value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self.coordinator.apply_local_state(self._device.device_id, {INST_POWER: 0})
        await self._send(CAP_ON_OFF, INST_POWER, 0)
