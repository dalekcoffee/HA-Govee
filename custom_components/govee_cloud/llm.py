"""Give LLM conversation agents (like Claude) the named-colour tool.

Since Home Assistant 2026.10, agents only see intents that an integration
offers through this platform; registering the intent is no longer enough.
"""

from __future__ import annotations

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    ToolAnnotations,
)

from .const import DOMAIN
from .voice import INTENT_SET_COLOR, INTENT_SET_POWER

TOOLS = {
    INTENT_SET_COLOR: "Set Govee light colour",
    INTENT_SET_POWER: "Turn Govee lights on or off",
}

# Calling again with the same arguments changes nothing more.
ANNOTATIONS = ToolAnnotations(idempotent=True, open_world=False)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Offer the Govee tools when any Govee light is exposed to the assistant."""
    if api_id != LLM_API_ASSIST or not llm_context.assistant:
        return None

    registry = er.async_get(hass)
    if not any(
        entry.platform == DOMAIN
        and async_should_expose(hass, llm_context.assistant, entry.entity_id)
        for entry in registry.entities.values()
        if entry.domain == "light"
    ):
        return None

    tools = [
        IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            title=TOOLS[handler.intent_type],
            integration=DOMAIN,
            annotations=ANNOTATIONS,
        )
        for handler in intent.async_get(hass)
        if handler.intent_type in TOOLS
    ]
    return LLMTools(tools=tools) if tools else None
