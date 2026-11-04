"""Shared test data."""

BASE = "https://openapi.api.govee.com/router/api/v1"
DEVICE_ID = "AA:BB:CC:DD:EE:FF:00:11"
API_KEY = "test-key"

DEVICES = {
    "code": 200,
    "message": "success",
    "data": [
        {
            "sku": "H6008",
            "device": DEVICE_ID,
            "deviceName": "Bedroom bulb",
            "type": "devices.types.light",
            "capabilities": [
                {
                    "type": "devices.capabilities.on_off",
                    "instance": "powerSwitch",
                    "parameters": {
                        "dataType": "ENUM",
                        "options": [
                            {"name": "on", "value": 1},
                            {"name": "off", "value": 0},
                        ],
                    },
                },
                {
                    "type": "devices.capabilities.range",
                    "instance": "brightness",
                    "parameters": {
                        "unit": "unit.percent",
                        "dataType": "INTEGER",
                        "range": {"min": 1, "max": 100, "precision": 1},
                    },
                },
                {
                    "type": "devices.capabilities.color_setting",
                    "instance": "colorRgb",
                    "parameters": {
                        "dataType": "INTEGER",
                        "range": {"min": 0, "max": 16777215, "precision": 1},
                    },
                },
                {
                    "type": "devices.capabilities.color_setting",
                    "instance": "colorTemperatureK",
                    "parameters": {
                        "dataType": "INTEGER",
                        "range": {"min": 2000, "max": 9000, "precision": 1},
                    },
                },
            ],
        },
        {
            "sku": "H5075",
            "device": "11:22:33:44:55:66:77:88",
            "deviceName": "Thermometer",
            "type": "devices.types.thermometer",
            "capabilities": [],
        },
    ],
}


def state(power=1, brightness=50, rgb=0xFF0000, kelvin=0, online=True):
    """Build a state response."""
    return {
        "requestId": "x",
        "msg": "success",
        "code": 200,
        "payload": {
            "sku": "H6008",
            "device": DEVICE_ID,
            "capabilities": [
                {
                    "type": "devices.capabilities.online",
                    "instance": "online",
                    "state": {"value": online},
                },
                {
                    "type": "devices.capabilities.on_off",
                    "instance": "powerSwitch",
                    "state": {"value": power},
                },
                {
                    "type": "devices.capabilities.range",
                    "instance": "brightness",
                    "state": {"value": brightness},
                },
                {
                    "type": "devices.capabilities.color_setting",
                    "instance": "colorRgb",
                    "state": {"value": rgb},
                },
                {
                    "type": "devices.capabilities.color_setting",
                    "instance": "colorTemperatureK",
                    "state": {"value": kelvin},
                },
            ],
        },
    }
