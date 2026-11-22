# Vestel Akıllı Yaşam for Home Assistant

[![Validation](https://github.com/halilyildiz/vestel-akilli-yasam/actions/workflows/validate.yaml/badge.svg)](https://github.com/halilyildiz/vestel-akilli-yasam/actions/workflows/validate.yaml)
[![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=halilyildiz&repository=vestel-akilli-yasam&category=integration)

Unofficial cloud integration for appliances paired with **Vestel Akıllı Yaşam / Smart Life (homevsmart)**. Not affiliated with, endorsed by, or supported by Vestel. This is a community integration, not the official mobile app.

[Türkçe kurulum ve kullanım](README.tr.md)

## Supported appliances

| Cloud type | Appliance | Controls and status |
| --- | --- | --- |
| AC | Air conditioner | HVAC mode, temperature, fan, supported extras and timers |
| WD | Washer-dryer | Programs, supported wash/dry options, start/pause and progress |
| DW | Dishwasher | Programs, supported options, start/pause/cancel and progress |
| RF | Refrigerator | Compartment targets, supported modes, child lock and screen saver |

Capabilities come from each appliance's cloud discovery document. Support is limited to these families using the implemented legacy register protocol. Other Vestel products and every model are **not** guaranteed to work. Standalone washers, dryers, ovens, vacuums and other unsupported cloud types are not currently supported. Incompatible descriptions are isolated and reported through Home Assistant Repairs.

## Requirements

- Home Assistant **2026.11.0 or newer**.
- An existing Akıllı Yaşam account, with appliances already paired in the official app.
- Internet access to the Vestel/homevsmart and Amazon Cognito/IoT services used by that account.
- Remote control enabled on the appliance panel where the manufacturer requires it.

## Install

Use the Marketplace button above. Until this repository is accepted into the public catalog, add it as a **custom repository**, category **Integration**:

`https://github.com/halilyildiz/vestel-akilli-yasam`

Install **Vestel Akıllı Yaşam**, follow any restart prompt, then open Settings → Devices & services → Add integration → **Vestel Akıllı Yaşam**. Sign in with the email/password from the mobile app and choose your existing home. There is no dependency on an older Vestel integration or a discovery helper.

[![Start setup](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vestel_appliances)

For a manual install, copy `custom_components/vestel_appliances` into your Home Assistant configuration directory and restart. If upgrading an existing manual installation of **this** integration, keep its config entry: the domain and unique IDs remain `vestel_appliances`, so entity preferences and references can be preserved.

## Updates and entities

- Supported devices added to the selected app home are discovered on the next successful poll, normally within 45 seconds. New entities do not require a reload.
- MQTT events request a fresh cloud reading. If live updates fail, polling continues. Subscription sessions refresh when the device set changes.
- Firmware/model revision changes cause discovery definitions to be refreshed. A malformed model must not prevent other appliances from working.
- Primary operating state, remaining time, warnings and controls are enabled. Technical diagnostics and estimated daily/monthly energy, water and cost sensors are disabled by default. Estimates are not meter measurements.
- Selected-program sensors remain available because program selection controls can become unavailable while a cycle is running.
- Removed devices are retained as unavailable instead of deleting their registry entries automatically.

## Actions

The integration provides `vestel_appliances.apply`, `get_consumption`, `get_billing_settings`, `set_bill_limit`, `set_energy_price`, `set_subscriber_type`, `set_tariff_type` and `set_energy_management`. Their fields are available in the Home Assistant action editor. Appliance actions validate discovery limits and current state; there is no unrestricted raw-command action.

A cloud acknowledgement is followed by a readback. A delayed confirmation is not reported as a successful physical operation and does not trigger an automatic command replay. Billing settings modify the cloud account; consumption values are estimates.

## Troubleshooting and privacy

Check connectivity and remote-control permission in the official app first. For an unsupported type or model description, look under Settings → System → Repairs. Download the integration's redacted diagnostics before reporting a bug, and inspect the file yourself before attaching it. Do not post account passwords, tokens, unredacted captures, MAC addresses or serial numbers.

Account credentials and refresh tokens are stored by Home Assistant's config-entry mechanism. The integration does not transmit them to this repository or its maintainer. Authentication goes to the cloud provider; there is no direct local-only control mode. Cloud API changes can break the integration.

## Development and validation

```sh
python -m unittest discover -s tests -v
```

The offline suite currently has 103 tests. It uses protocol descriptions with synthetic appliance metadata and register examples; it makes no appliance or cloud calls. Most HA modules are test doubles, so this suite is not a substitute for Home Assistant runtime testing. The maintainer has tested four household appliances; other physical models are not certified by these tests.

GitHub Actions runs the offline tests, Home Assistant hassfest and HACS validation. Catalog acceptance is a separate review by its maintainers and must not be inferred from a successful custom-repository install.

## Uninstall

Remove the integration entry from Settings → Devices & services, then uninstall its repository through Marketplace and follow the restart prompt. Removing an entry also removes its Home Assistant entities; automations referring to them need updating. Your appliance pairings in the official app are separate.

## License and acknowledgements

Code is released under the [MIT license](LICENSE). See [third-party notices](NOTICE.md) for upstream acknowledgements and the separate status of the Vestel application artwork.
