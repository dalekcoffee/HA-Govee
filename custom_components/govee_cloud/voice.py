"""Voice control: named colours, "all lights", and local sentences.

Two pieces, both optional extras on top of the normal light entities:

* An intent (GoveeSetLightColor) that Assist and LLM agents such as Claude
  can call to set lights to a named colour, including names Home Assistant
  doesn't know ("dark brown", "candlelight"). With no room it sets every
  Govee light.
* Sentences matched locally by Home Assistant's own voice engine, so common
  commands like "set all lights to dark brown" run without an LLM. These
  need "Prefer handling commands locally" on in the voice pipeline (or the
  Home Assistant conversation agent).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    intent,
)

from .compat import vol
from .const import DOMAIN
from .light import preset_kwargs
from .palette import Preset, normalize, resolve, spoken_names

if TYPE_CHECKING:
    from .light import GoveeLight

_LOGGER = logging.getLogger(__name__)

INTENT_SET_COLOR = "GoveeSetLightColor"

ALL_WORDS = {"all", "all the", "every", "everything", "every single"}

DATA_VOICE = f"{DOMAIN}_voice"


def _loaded_lights(hass: HomeAssistant) -> list[GoveeLight]:
    lights: list[GoveeLight] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            lights.extend(entry.runtime_data.lights)
    return lights


def _area_ids(hass: HomeAssistant, name: str) -> set[str]:
    areas = ar.async_get(hass)
    found = {a.id for a in areas.async_get_areas_by_alias(name)}
    if (area := areas.async_get_area_by_name(name)) is not None:
        found.add(area.id)
    return found


def _light_area(hass: HomeAssistant, light: GoveeLight) -> str | None:
    if light.entity_id is None:
        return None
    entry = er.async_get(hass).async_get(light.entity_id)
    if entry is None:
        return None
    if entry.area_id:
        return entry.area_id
    if entry.device_id and (device := dr.async_get(hass).async_get(entry.device_id)):
        return device.area_id
    return None


def find_lights(hass: HomeAssistant, area: str | None) -> list[GoveeLight]:
    """Lights in a named area, or every light when no area is given."""
    lights = _loaded_lights(hass)
    if area is None or normalize(area) in ALL_WORDS:
        return lights
    area_ids = _area_ids(hass, normalize(area))
    return [light for light in lights if _light_area(hass, light) in area_ids]


async def apply_preset(lights: list[GoveeLight], preset: Preset) -> None:
    """Set every light to the preset at once (each light paces itself)."""
    kwargs = preset_kwargs(preset)
    results = await asyncio.gather(
        *(light.async_turn_on(**kwargs) for light in lights),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            _LOGGER.warning("A Govee light did not respond: %s", result)


class SetColorIntent(intent.IntentHandler):
    """Set Govee lights to a named colour."""

    intent_type = INTENT_SET_COLOR
    platforms: ClassVar[set[str]] = {"light"}
    description = (
        "Sets Govee lights to a named colour or white tone, including names "
        "like dark brown, brown, warm white or candlelight. Use this for "
        "colour requests. Leave area empty when the user says all lights or "
        "every light, to set every light in the house."
    )
    slot_schema: ClassVar[dict] = {
        vol.Required("color"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        color = slots["color"]["value"]
        area = slots.get("area", {}).get("value")
        preset = resolve(color)
        if preset is None:
            raise intent.IntentHandleError(f"I don't know the colour {color}")
        lights = find_lights(intent_obj.hass, area)
        if not lights:
            raise intent.IntentHandleError(f"No Govee lights found in {area}")
        await apply_preset(lights, preset)
        response = intent_obj.create_response()
        response.async_set_speech("Done")
        return response


def _sentences() -> list[str]:
    colors = "(" + "|".join(spoken_names()) + ")"
    verbs = "(set|turn|make|change)"
    return [
        f"{verbs} (all [the]|every [single]) light[s] [to] {colors}",
        f"{verbs} everything [to] {colors}",
        f"{verbs} [the] {{area}} light[s] [to] {colors}",
    ]


def _color_in(text: str) -> str | None:
    text = f" {normalize(text)} "
    for name in spoken_names():
        if f" {name} " in text:
            return name
    return None


def _make_sentence_handler(hass: HomeAssistant):
    async def on_sentence(user_input: Any, result: Any) -> str | None:
        color = _color_in(user_input.text)
        preset = resolve(color) if color else None
        if preset is None:
            return None
        area_entity = result.entities.get("area")
        area = area_entity.text.strip() if area_entity else None
        lights = find_lights(hass, area)
        if not lights:
            return f"I couldn't find any Govee lights in {area}"
        await apply_preset(lights, preset)
        return "Done"

    return on_sentence


def async_setup_voice(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Register the intent and local sentences. Returns an unregister callback."""
    if DATA_VOICE in hass.data:
        hass.data[DATA_VOICE]["users"] += 1
        return lambda: _release(hass)

    intent.async_register(hass, SetColorIntent())
    unregister_trigger: CALLBACK_TYPE | None = None
    try:
        unregister_trigger = _register_sentences(hass)
    except Exception:
        _LOGGER.warning(
            "Could not register local voice sentences; colour commands will "
            "still work through your conversation agent",
            exc_info=True,
        )

    hass.data[DATA_VOICE] = {"users": 1, "unregister": unregister_trigger}
    return lambda: _release(hass)


def _register_sentences(hass: HomeAssistant) -> CALLBACK_TYPE:
    # Not a public API, but it's how conversation triggers register their
    # sentences. If it changes, the intent still works through Assist.
    from homeassistant.components.conversation.agent_manager import (
        get_agent_manager,
    )

    manager = get_agent_manager(hass)
    handler = _make_sentence_handler(hass)
    try:
        # Home Assistant 2025.x
        from homeassistant.components.conversation.trigger import TriggerDetails
    except ImportError:
        # Home Assistant 2026.10 and later
        return manager.register_trigger(_sentences(), handler)
    return manager.register_trigger(TriggerDetails(_sentences(), handler))


def _release(hass: HomeAssistant) -> None:
    data = hass.data.get(DATA_VOICE)
    if data is None:
        return
    data["users"] -= 1
    if data["users"] > 0:
        return
    if data["unregister"] is not None:
        data["unregister"]()
    intent.async_remove(hass, INTENT_SET_COLOR)
    hass.data.pop(DATA_VOICE)
