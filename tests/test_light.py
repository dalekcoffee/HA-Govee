"""Light platform tests."""

import asyncio
import copy
import json

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.govee_cloud.api import GoveeRateLimitError
from custom_components.govee_cloud.const import CONF_DEVICES, DOMAIN

from .common import API_KEY, BASE, DEVICE_ID, DEVICES, state

ENTITY = "light.bedroom_bulb"


async def _setup(hass, aioclient_mock, **state_kwargs):
    aioclient_mock.get(f"{BASE}/user/devices", json=DEVICES)
    aioclient_mock.post(f"{BASE}/device/state", json=state(**state_kwargs))
    aioclient_mock.post(f"{BASE}/device/control", json={"code": 200, "msg": "success"})
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: API_KEY, CONF_DEVICES: [DEVICE_ID]}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _controls(aioclient_mock):
    sent = []
    for method, url, data, _headers in aioclient_mock.mock_calls:
        if str(url).endswith("/device/control"):
            body = data if isinstance(data, dict) else json.loads(data)
            cap = body["payload"]["capability"]
            sent.append((cap["instance"], cap["value"]))
    return sent


async def test_state(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    st = hass.states.get(ENTITY)
    assert st.state == STATE_ON
    assert st.attributes[ATTR_RGB_COLOR] == (255, 0, 0)
    assert st.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert st.attributes[ATTR_BRIGHTNESS] == 128


async def test_color_temp_state(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, kelvin=4000)
    st = hass.states.get(ENTITY)
    assert st.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert st.attributes[ATTR_COLOR_TEMP_KELVIN] == 4000


async def test_offline_is_unavailable(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, online=False)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


async def test_turn_on_with_color_and_brightness(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, power=0)
    assert hass.states.get(ENTITY).state == STATE_OFF
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: ENTITY, ATTR_RGB_COLOR: (0, 0, 255), ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    assert _controls(aioclient_mock) == [
        ("powerSwitch", 1),
        ("colorRgb", 0x0000FF),
        ("brightness", 100),
    ]
    st = hass.states.get(ENTITY)
    assert st.state == STATE_ON
    assert st.attributes[ATTR_RGB_COLOR] == (0, 0, 255)


async def test_turn_on_color_temp_clamped(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: ENTITY, ATTR_COLOR_TEMP_KELVIN: 1500},
        blocking=True,
    )
    assert _controls(aioclient_mock) == [("colorTemperatureK", 2000)]


async def test_turn_off(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: ENTITY}, blocking=True
    )
    assert _controls(aioclient_mock) == [("powerSwitch", 0)]
    assert hass.states.get(ENTITY).state == STATE_OFF


async def test_auth_failure_starts_reauth(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/user/devices", status=401, json={})
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: API_KEY, CONF_DEVICES: [DEVICE_ID]}
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_turn_on_sends_power_even_if_cached_on(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, power=1)
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: ENTITY}, blocking=True
    )
    assert _controls(aioclient_mock) == [("powerSwitch", 1)]


async def test_rate_limit_stops_polling(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/user/devices", json=DEVICES)
    aioclient_mock.post(f"{BASE}/device/state", status=429, json={})
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


async def test_rate_limited_command_is_retried(hass, aioclient_mock, monkeypatch):
    monkeypatch.setattr("custom_components.govee_cloud.light.RATE_LIMIT_RETRY_DELAY", 0)
    entry = await _setup(hass, aioclient_mock)
    api = entry.runtime_data.api
    calls = []

    async def flaky_control(device, cap_type, instance, value):
        calls.append((instance, value))
        if len(calls) == 1:
            raise GoveeRateLimitError("429")

    monkeypatch.setattr(api, "control", flaky_control)
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: ENTITY}, blocking=True
    )
    assert calls == [("powerSwitch", 0), ("powerSwitch", 0)]
    assert hass.states.get(ENTITY).state == STATE_OFF


async def test_stale_poll_does_not_undo_new_color(hass, aioclient_mock):
    entry = await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: ENTITY, ATTR_RGB_COLOR: (0, 255, 0)},
        blocking=True,
    )
    # Govee still reports the old red color on the next poll.
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes[ATTR_RGB_COLOR] == (0, 255, 0)


async def test_newest_drag_value_wins(hass, aioclient_mock, monkeypatch):
    entry = await _setup(hass, aioclient_mock)
    api = entry.runtime_data.api
    release = asyncio.Event()
    sent = []

    async def slow_control(device, cap_type, instance, value):
        sent.append(value)
        if len(sent) == 1:
            await release.wait()

    monkeypatch.setattr(api, "control", slow_control)
    calls = [
        hass.async_create_task(
            hass.services.async_call(
                LIGHT_DOMAIN,
                "turn_on",
                {ATTR_ENTITY_ID: ENTITY, ATTR_RGB_COLOR: rgb},
                blocking=True,
            )
        )
        for rgb in ((255, 0, 0), (0, 255, 0), (0, 0, 255))
    ]
    await asyncio.sleep(0.05)
    release.set()
    await asyncio.gather(*calls)
    await hass.async_block_till_done()
    # The first value went out, the middle one was merged away, and the
    # picker stays on the last value.
    assert sent == [0xFF0000, 0x0000FF]
    assert hass.states.get(ENTITY).attributes[ATTR_RGB_COLOR] == (0, 0, 255)


async def test_brown_sends_google_orange(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: ENTITY, "color_name": "brown"},
        blocking=True,
    )
    assert _controls(aioclient_mock) == [
        ("colorRgb", (255 << 16) | (120 << 8) | 20),
    ]


async def test_explicit_brightness_wins_over_color_darkness(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: ENTITY, "color_name": "brown", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    assert _controls(aioclient_mock)[-1] == ("brightness", 100)


async def test_govee_app_group_is_skipped(hass, aioclient_mock):
    """A group made in the Govee app is never set up, even if selected before."""
    group_id = "GROUP-1234"
    devices = copy.deepcopy(DEVICES)
    group = copy.deepcopy(devices["data"][0])
    group.update(sku="SameModeGroup", device=group_id, deviceName="Bonfire")
    group.pop("type")
    devices["data"].append(group)
    aioclient_mock.get(f"{BASE}/user/devices", json=devices)
    aioclient_mock.post(f"{BASE}/device/state", json=state())
    aioclient_mock.post(f"{BASE}/device/control", json={"code": 200, "msg": "success"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY, CONF_DEVICES: [DEVICE_ID, group_id]},
    )
    entry.add_to_hass(hass)
    stale = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, group_id)}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.bonfire") is None
    assert dr.async_get(hass).async_get(stale.id) is None
