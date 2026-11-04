# Govee Cloud for Home Assistant

Control Govee lights that don't have LAN Control (like the H6008 bulb) through Govee's **official** cloud API.

## How to install

**1. Get a Govee API key**
In the Govee Home app, go to **Settings › Apply for API Key**. Govee emails you the key.

**2. Add the integration to Home Assistant**
1. Open **Settings › Marketplace** (called **HACS** before HA 2026.11).
2. Open the **⋮** menu and choose **Custom repositories**.
3. Paste `https://github.com/dalekcoffee/HA-Govee`, set the type to **Integration**, and click **Add**.
4. Search for **Govee Cloud** and click **Download**.
5. Restart Home Assistant (**Settings › System › ⋮ › Restart**).

**3. Set it up**
1. Go to **Settings › Devices & services › Add Integration**.
2. Search for **Govee Cloud**.
3. Paste your API key and tick the lights you want.

Your lights then show up as normal HA lights. To change which lights are included later, open the integration and click **Configure**.

<details>
<summary>Installing without the Marketplace</summary>

1. Copy the `custom_components/govee_cloud` folder from this repo into `/config/custom_components/` on your HA box. The **File editor** or **Samba** app works for this.
2. Restart Home Assistant, then follow step 3 above.

You won't get update notifications this way.
</details>

## Good to know

- **What it controls:** on/off, brightness, color and color temperature.
- **Updates:** HA checks each light once a minute, so changes made in the Govee app can take up to a minute to show in HA.
- **Lights with LAN Control:** keep using the built-in **Govee lights local** integration for those, and leave them unticked here.
- **Internet:** it needs internet access and Govee's cloud to be up.

## Privacy

- **Where it connects:** the only server it talks to is `openapi.api.govee.com`.
- **What it sends:** only your API key, which HA stores locally. The key is never in this repo.
- **What it doesn't use:** no Govee password, no MQTT, no third-party services and no extra Python packages.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```
