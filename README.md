# Govee Cloud for Home Assistant

A small custom integration that controls Govee lights through Govee's **official** Developer Platform API (`openapi.api.govee.com`). It's meant for lights that don't offer LAN Control, like the H6008 bulb. For lights that do have LAN Control, use the built-in **Govee lights local** integration instead.

## What it does

- Turns lights on and off and sets brightness, RGB color and color temperature.
- Polls each selected light once a minute. Govee allows 30 state requests per light per minute.
- Lets you pick which lights to add, so lights you already control locally don't show up twice.
- Asks for a new key if Govee starts rejecting the stored one.

## What it doesn't do

- **Scenes, music modes and segment colors.** These aren't supported yet.
- **Instant updates.** Changes made in the Govee app show up in HA at the next poll, within about a minute.
- **Offline control.** It needs the internet and Govee's cloud to be up.

## Privacy

- The only host it talks to is `openapi.api.govee.com`.
- It sends only your API key, in the `Govee-API-Key` header.
- It uses no Govee account password, no MQTT and no third-party services.
- It has no Python dependencies outside Home Assistant itself.

## Install

1. Get an API key: in the Govee Home app, go to **Settings › Apply for API Key**. Govee emails the key to you.
2. In Home Assistant, open **Settings › Marketplace** (HACS on versions before 2026.11). Add this repository as a **custom repository** with the type **Integration**, then download **Govee Cloud**.
3. Restart Home Assistant.
4. Go to **Settings › Devices & services › Add Integration › Govee Cloud**. Paste your key, then choose your lights.

To change which lights are included later, open the integration and click **Configure**.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```
