"""LLM tool tests (Home Assistant 2026.10 and later)."""

import pytest

pytest.importorskip("homeassistant.components.llm")

from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.core import Context
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from .test_voice import DEVICE_2, _controls, _setup

from .common import DEVICE_ID

TOOL = "govee_cloud__GoveeSetLightColor"


def _context():
    return llm.LLMContext(
        platform="test",
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def test_colour_tool_offered_and_works(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    assert await async_setup_component(hass, "llm", {})
    async_expose_entity(hass, "conversation", "light.bedroom_bulb", True)

    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    tools = {tool.name: tool for tool in api.tools}
    assert TOOL in tools

    start = len(aioclient_mock.mock_calls)
    await api.async_call_tool(
        llm.ToolInput(tool_name=TOOL, tool_args={"color": "warm white"})
    )
    await hass.async_block_till_done()
    assert {d for d, _ in _controls(aioclient_mock, start)} == {DEVICE_ID, DEVICE_2}


async def test_colour_tool_hidden_when_nothing_exposed(hass, aioclient_mock):
    await _setup(hass, aioclient_mock)
    assert await async_setup_component(hass, "llm", {})
    for entity_id in hass.states.async_entity_ids("light"):
        async_expose_entity(hass, "conversation", entity_id, False)

    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    assert TOOL not in {tool.name for tool in api.tools}
