# Vestel Smart Life for Home Assistant

Control supported **air conditioners, washer-dryers, dishwashers and refrigerators** from Home Assistant using your Vestel Akıllı Yaşam account. See appliance status and program progress alongside the controls each model supports.

[**Türkçe**](README.tr.md) · [Installation](#installation) · [Troubleshooting](docs/troubleshooting.md) · [Updating](docs/upgrading.md)

[![Validation](https://github.com/halilyildiz/vestel-smart-life-home-assistant/actions/workflows/validate.yaml/badge.svg)](https://github.com/halilyildiz/vestel-smart-life-home-assistant/actions/workflows/validate.yaml)
[![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=halilyildiz&repository=vestel-smart-life-home-assistant&category=integration)

Unofficial community integration; not affiliated with or supported by Vestel. It connects to **Vestel Akıllı Yaşam / Smart Life (homevsmart)**, not Tuya Smart Life.

Built on [Mehmet Aktaş's MIT-licensed Vestel Smart Home integration](https://github.com/mehmetaktas/ha-vestel-smarthome), with authentication and cloud communication adapted and extended for additional appliance families. [Source acknowledgements](NOTICE.md).

This page describes `main`; check the [release notes](https://github.com/halilyildiz/vestel-smart-life-home-assistant/releases) for your installed version. **Already using an older version? Read the [migration guide](docs/upgrading.md) before updating**, especially if automations use option names or fan modes.

## Will it work with my appliance?

| Appliance | Available features depend on the model |
| --- | --- |
| Air conditioner | Operating mode, target temperature, fan, supported extras and timers |
| Washer-dryer | Program selection, wash/dry options, start/pause and progress |
| Dishwasher | Program selection, options, start/pause/cancel and progress |
| Refrigerator | Compartment temperature targets, supported modes, child lock and screen saver |
| Standalone washing machine (`WM`, experimental) | Discovery-defined programs/options, start/pause, remote-control and phase restrictions |
| French-door refrigerator (`FD`, experimental) | Discovery-defined zone temperature/mode controls and status |
| Standalone tumble dryer (`TD`, monitoring only) | Cloud-reported state, phase, remaining time and faults; no controls |
| Oven (`OV`, monitoring only) | Cloud-reported program, state, temperature, remaining time and faults; no controls |

The appliance must already be paired with your account in the supported Vestel app and expose a compatible legacy-register discovery schema. The new WM/FD/TD/OV coverage is **unreleased and verified offline against APK demo descriptions, not physical appliances**. JSON/HCA variants, third-party/Tuya/Dreame devices, TVs, chargers and other families are not yet controlled by this integration. A Vestel-manufactured product sold under another brand or in another region is not automatically compatible. See the [protocol evidence and remaining work](docs/device-families.md).

Support is based on the appliance's cloud capability description. A model/firmware compatibility list is not yet published, so support for every model is not guaranteed. This integration **needs internet access**; it does not provide local-only control.

## Installation

Before you start, you need **Home Assistant 2026.11.0 or newer**, HACS, and the email/password you use in the Vestel app. Enable remote control on the appliance panel if the manufacturer requires it.

1. Open **HACS** (Marketplace in some installations), then its menu → **Custom repositories**.
2. Add the address below with category **Integration**:

   `https://github.com/halilyildiz/vestel-smart-life-home-assistant`

3. Find and install **Vestel Smart Life**, then follow any restart prompt.
4. Open **Settings → Devices & services → Add integration → Vestel Smart Life**.
5. Sign in with your Vestel account and select the home containing your appliances.

The repository can be installed as a custom repository before public catalog acceptance. English and Turkish interface translations follow Home Assistant's language settings.

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vestel_appliances)

**Manual installation:** copy the entire `custom_components/vestel_appliances` folder, including its license and notice files, into `<your Home Assistant config>/custom_components/vestel_appliances`, restart, then follow steps 4–5.

## First use

Open **Settings → Devices & services → Vestel Smart Life**, then select an appliance. Its device page lists the controls and status entities available for that model; you can add them to your dashboard using Home Assistant's card editor. No YAML is needed for normal use.

| What you want to do | Where to start |
| --- | --- |
| Change the air conditioner temperature | Open its climate entity and choose a supported mode and temperature. |
| Select a washing/dishwashing program | Use the program select entity while the appliance is ready and remote control is enabled. |
| Check a running program | Use operating state, selected program and remaining-time sensors; some settings are locked during a cycle. |
| Show consumption estimates | Open the device's entity list, enable the optional daily/monthly consumption entities, and allow the background history query to finish. These are estimates, not meter readings. |

New supported appliances added to the selected app home normally appear after the next successful check, about every 45 seconds. Live cloud events also trigger updates. Appliance controls start without waiting for energy history.

## If something does not work

- **Cannot connect:** check the official app and internet access. Temporary cloud outages or rate limits can recover on a later check.
- **Appliance or control unavailable:** check the selected home, panel remote-control permission and **Settings → System → Repairs**.
- **Command accepted but not confirmed:** check the actual appliance and official app before retrying; the integration does not automatically resend an unconfirmed command.

See the [full troubleshooting guide](docs/troubleshooting.md). For ordinary bugs, include the installed integration/HA versions, device model and steps in an [issue](https://github.com/halilyildiz/vestel-smart-life-home-assistant/issues). Download diagnostics from the integration menu and **inspect them before sharing**.

## Privacy

Your email, password and refresh tokens are stored by Home Assistant and used to authenticate with the vendor cloud. Protect configuration files and backups. Diagnostics mask known sensitive information, but you should still review them. See [privacy details](docs/troubleshooting.md) and [SECURITY.md](SECURITY.md) for private vulnerability reporting.

## More guides

- [Advanced actions and billing settings](docs/advanced.md)
- [Updating, option-name changes and migration from other integrations](docs/upgrading.md)
- [Development, tests and update behavior](docs/development.md)
- [Troubleshooting, privacy and uninstalling](docs/troubleshooting.md)

## License and credits

Code is distributed under the [MIT license](LICENSE). The original work by **Mehmet Aktaş** is credited in [NOTICE.md](NOTICE.md), and his [complete MIT notice](licenses/ha-vestel-smarthome-MIT.txt) is retained. The installable folder includes [both MIT notices](custom_components/vestel_appliances/LICENSE) and its [NOTICE.md](custom_components/vestel_appliances/NOTICE.md); keep them when redistributing it. Vestel artwork has separate ownership and is not covered by this project's MIT grant.
