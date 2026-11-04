"""Config flow tests."""

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.govee_cloud.const import CONF_DEVICES, DOMAIN

from .common import API_KEY, BASE, DEVICE_ID, DEVICES, state


async def test_user_flow(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/user/devices", json=DEVICES)
    aioclient_mock.post(f"{BASE}/device/state", json=state())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "devices"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICES: [DEVICE_ID]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: API_KEY, CONF_DEVICES: [DEVICE_ID]}
    # Only the light was set up, not the thermometer.
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("light")) == 1


async def test_invalid_key(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/user/devices", status=401, json={})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/user/devices", status=500, json={"code": 500})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_wrong_account(hass, aioclient_mock):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "old", CONF_DEVICES: ["not-on-this-account"]}
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE}/user/devices", json=DEVICES)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["errors"] == {"base": "wrong_account"}


async def test_reauth_success(hass, aioclient_mock):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "old", CONF_DEVICES: [DEVICE_ID]}
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE}/user/devices", json=DEVICES)
    aioclient_mock.post(f"{BASE}/device/state", json=state())
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == API_KEY
