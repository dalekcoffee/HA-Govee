"""Constants for the Govee Cloud integration."""

from datetime import timedelta

DOMAIN = "govee_cloud"

API_BASE_URL = "https://openapi.api.govee.com"

CONF_DEVICES = "devices"

# Govee allows 30 state requests per minute per device; one poll a minute
# per device stays far below that.
SCAN_INTERVAL = timedelta(seconds=60)

TYPE_LIGHT = "devices.types.light"
CAP_ONLINE = "devices.capabilities.online"
CAP_ON_OFF = "devices.capabilities.on_off"
CAP_RANGE = "devices.capabilities.range"
CAP_COLOR = "devices.capabilities.color_setting"

INST_ONLINE = "online"
INST_POWER = "powerSwitch"
INST_BRIGHTNESS = "brightness"
INST_RGB = "colorRgb"
INST_COLOR_TEMP = "colorTemperatureK"
