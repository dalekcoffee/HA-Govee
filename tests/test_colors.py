"""Colour adaptation tests."""

import colorsys

from custom_components.govee_cloud.colors import adapt_rgb


def _hue_degrees(rgb):
    return colorsys.rgb_to_hsv(*(c / 255 for c in rgb))[0] * 360


def test_brown_is_dim_warm_orange():
    bulb, brightness = adapt_rgb((165, 42, 42))
    assert 15 <= _hue_degrees(bulb) <= 35  # orange, not red/pink
    assert brightness <= 30


def test_saddlebrown_is_dimmer_than_brown():
    _, brown = adapt_rgb((165, 42, 42))
    _, dark = adapt_rgb((139, 69, 19))
    assert dark < brown


def test_full_intensity_colors_unchanged():
    assert adapt_rgb((255, 0, 0)) == ((255, 0, 0), None)
    assert adapt_rgb((0, 128, 255)) == ((0, 128, 255), None)


def test_dark_color_becomes_brightness():
    bulb, brightness = adapt_rgb((139, 0, 0))  # darkred
    assert bulb == (255, 0, 0)
    assert brightness == 55


def test_black_is_dimmest():
    assert adapt_rgb((0, 0, 0))[1] == 1
