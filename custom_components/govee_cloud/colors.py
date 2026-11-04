"""Make Home Assistant colours look right on an RGB bulb.

Home Assistant turns colour names into web colours, and many of those are
"dark" colours: brown is RGB (165, 42, 42). A screen shows that as a dark
reddish brown, but a bulb can't show dark. It shows the same hue at full
output, so brown comes out as a bright pinky red.

On a light, darkness is brightness. So for any colour that isn't already at
full intensity, we send the hue at full intensity and turn the darkness
into a lower brightness. Earthy colours also get a warmer hue, because LEDs
read reddish browns as pink. This matches how other assistants render
"brown" on the same bulbs: a dim, warm orange.
"""

from __future__ import annotations

import colorsys

RGB = tuple[int, int, int]

# Web colours that look wrong on LEDs, mapped to what they look like in a
# room: (bulb colour, brightness %). Keys are Home Assistant's values for
# these colour names (homeassistant.util.color.COLORS).
EARTH_TONES: dict[RGB, tuple[RGB, int]] = {
    (165, 42, 42): ((255, 85, 10), 25),  # brown
    (139, 69, 19): ((255, 80, 5), 18),  # saddlebrown ("dark brown")
    (160, 82, 45): ((255, 95, 20), 28),  # sienna
    (210, 105, 30): ((255, 110, 15), 45),  # chocolate
    (128, 0, 0): ((255, 20, 0), 20),  # maroon
    (205, 133, 63): ((255, 140, 45), 50),  # peru
    (210, 180, 140): ((255, 175, 95), 60),  # tan
    (222, 184, 135): ((255, 180, 100), 70),  # burlywood
}

# Colours at or above this intensity are left alone (the colour wheel always
# sends full-intensity colours).
FULL_INTENSITY = 0.95


def adapt_rgb(rgb: RGB) -> tuple[RGB, int | None]:
    """Return (bulb colour, brightness % or None to leave brightness alone)."""
    if rgb in EARTH_TONES:
        return EARTH_TONES[rgb]

    red, green, blue = (c / 255 for c in rgb)
    hue, sat, value = colorsys.rgb_to_hsv(red, green, blue)
    if value <= 0:
        # Black: the dimmest setting is the closest a bulb can get.
        return rgb, 1
    if value >= FULL_INTENSITY:
        return rgb, None

    full = colorsys.hsv_to_rgb(hue, sat, 1.0)
    bulb = (round(full[0] * 255), round(full[1] * 255), round(full[2] * 255))
    return bulb, max(1, round(value * 100))
