"""Voice control tests."""

import json

from homeassistant.components import conversation
from homeassistant.const import CONF_API_KEY
from homeassistant.core import Context
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.govee_cloud.const import CONF_DEVICES, DOMAIN

from .common import API_KEY, BASE, DEVICE_ID, DEVICES, state

DEVICE_2 = "AA:BB:CC:DD:EE:FF:00:22"


def _two_lights():
    devices = json.loads(json.dumps(DEVICES))
    second = json.loads(json.dumps(devices["data"][0]))
    second["device"] = DEVICE_2
    second["deviceName"] = "Kitchen bulb"
    devices["data"].append(second)
    return devices


async def _setup(hass, aioclient_mock):
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "conversation", {})
    aioclient_mock.get(f"{BASE}/user/devices", json=_two_lights())
    aioclient_mock.post(f"{BASE}/device/state", json=state())
    aioclient_mock.post(f"{BASE}/device/control", json={"code": 200})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY, CONF_DEVICES: [DEVICE_ID, DEVICE_2]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _controls(aioclient_mock, start=0):
    sent = []
    for _method, url, data, _headers in aioclient_mock.mock_calls[start:]:
        if str(url).endswith("/device/control"):
            body = data if isinstance(data, dict) else json.loads(data)
            sent.append(
                (body["payload"]["device"], body["payload"]["capability"]["instance"])
            )
    return sent


async def test_all_lights_entity(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    st = hass.states.get("light.govee_cloud_all_lights")
    assert st is not None
    assert st.state == "on"
    start = len(aioclient_mock.mock_calls)
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.govee_cloud_all_lights"},
        blocking=True,
    )
    assert {d for d, _ in _controls(aioclient_mock, start)} == {DEVICE_ID, DEVICE_2}


async def test_intent_dark_brown_all(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    start = len(aioclient_mock.mock_calls)
    await intent.async_handle(
        hass, "test", "GoveeSetLightColor", {"color": {"value": "dark brown"}}
    )
    await hass.async_block_till_done()
    sent = _controls(aioclient_mock, start)
    assert (DEVICE_ID, "colorRgb") in sent
    assert (DEVICE_2, "brightness") in sent


async def test_intent_area(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    kitchen = ar.async_get(hass).async_create("Kitchen")
    er.async_get(hass).async_update_entity("light.kitchen_bulb", area_id=kitchen.id)
    start = len(aioclient_mock.mock_calls)
    await intent.async_handle(
        hass,
        "test",
        "GoveeSetLightColor",
        {"color": {"value": "warm white"}, "area": {"value": "kitchen"}},
    )
    assert {d for d, _ in _controls(aioclient_mock, start)} == {DEVICE_2}


async def test_local_sentence(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    start = len(aioclient_mock.mock_calls)
    result = await conversation.async_converse(
        hass, "set all lights to dark brown", None, Context(), language="en"
    )
    assert result.response.speech["plain"]["speech"] == "Done"
    assert {d for d, _ in _controls(aioclient_mock, start)} == {DEVICE_ID, DEVICE_2}


async def test_local_sentence_room(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    kitchen = ar.async_get(hass).async_create("Kitchen")
    er.async_get(hass).async_update_entity("light.kitchen_bulb", area_id=kitchen.id)
    start = len(aioclient_mock.mock_calls)
    await conversation.async_converse(
        hass, "set the kitchen lights to brown", None, Context(), language="en"
    )
    assert {d for d, _ in _controls(aioclient_mock, start)} == {DEVICE_2}


async def test_unknown_colour_is_not_handled_locally(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    start = len(aioclient_mock.mock_calls)
    await conversation.async_converse(
        hass, "set all lights to chartreuse sparkle", None, Context(), language="en"
    )
    assert _controls(aioclient_mock, start) == []
