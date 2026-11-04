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
from .voice import INTENT_SET_COLOR

# Setting a colour again with the same arguments changes nothing more.
ANNOTATIONS = ToolAnnotations(idempotent=True, open_world=False)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Offer the colour tool when any Govee light is exposed to the assistant."""
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

    handler = next(
        (h for h in intent.async_get(hass) if h.intent_type == INTENT_SET_COLOR),
        None,
    )
    if handler is None:
        return None
    return LLMTools(
        tools=[
            IntentTool(
                f"{DOMAIN}__{INTENT_SET_COLOR}",
                handler,
                title="Set Govee light colour",
                integration=DOMAIN,
                annotations=ANNOTATIONS,
            )
        ]
    )
