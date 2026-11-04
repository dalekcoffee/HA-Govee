"""Named colours that behave like other voice assistants.

Home Assistant only knows web colour names, and those look wrong on bulbs
("brown" is a pinky red, "dark brown" doesn't exist). These presets describe
what each name should look like in a room: a bulb colour or white
temperature, plus a brightness where the name implies one.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.util.color import color_name_to_rgb

from .colors import adapt_rgb


@dataclass(frozen=True)
class Preset:
    """How a colour name should look on a bulb."""

    rgb: tuple[int, int, int] | None = None
    kelvin: int | None = None
    # Brightness in percent, or None to keep the light's current brightness.
    brightness: int | None = None


# Calibrate these against how Google Home renders the same names.
PRESETS: dict[str, Preset] = {
    # Google Home shows "brown" as a warm orange (hue ~27 degrees) without
    # changing brightness; "dark brown" is the same hue, dimmed.
    "dark brown": Preset(rgb=(255, 105, 10), brightness=25),
    "brown": Preset(rgb=(255, 120, 20)),
    "light brown": Preset(rgb=(255, 140, 50)),
    "amber": Preset(rgb=(255, 126, 0)),
    "candlelight": Preset(kelvin=2000, brightness=30),
    "candle light": Preset(kelvin=2000, brightness=30),
    "warm white": Preset(kelvin=2700),
    "soft white": Preset(kelvin=2700),
    "white": Preset(kelvin=4000),
    "cool white": Preset(kelvin=5000),
    "daylight": Preset(kelvin=6500),
}

# Plain colour names that voice commands may handle without asking Claude.
COMMON_COLORS = [
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "magenta",
    "cyan",
    "teal",
    "turquoise",
    "lavender",
    "violet",
    "gold",
    "lime",
    "indigo",
    "coral",
    "salmon",
    "maroon",
    "navy",
]


def normalize(name: str) -> str:
    """Lower-case and collapse spaces."""
    return " ".join(name.lower().replace("-", " ").split())


def resolve(name: str) -> Preset | None:
    """Return the preset for a colour name, or None if it is unknown."""
    key = normalize(name)
    if key in PRESETS:
        return PRESETS[key]
    try:
        rgb = color_name_to_rgb(key)
    except ValueError:
        return None
    bulb, brightness = adapt_rgb(tuple(rgb))
    return Preset(rgb=bulb, brightness=brightness)


def spoken_names() -> list[str]:
    """Colour names the local voice sentences recognise, longest first."""
    return sorted({*PRESETS, *COMMON_COLORS}, key=len, reverse=True)
