# Vestel Akıllı Yaşam for Home Assistant

[![Validation](https://github.com/halilyildiz/vestel-akilli-yasam/actions/workflows/validate.yaml/badge.svg)](https://github.com/halilyildiz/vestel-akilli-yasam/actions/workflows/validate.yaml)
[![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=halilyildiz&repository=vestel-akilli-yasam&category=integration)

Unofficial cloud integration for appliances paired with **Vestel Akıllı Yaşam / Smart Life (homevsmart)**. Not affiliated with, endorsed by, or supported by Vestel. This is a community integration, not the official mobile app.

[Türkçe kurulum ve kullanım](README.tr.md)

This README describes the current `main` branch. Some changes may not yet be in a published release; check the [release notes](https://github.com/halilyildiz/vestel-akilli-yasam/releases) for the version installed on your system.

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

Install HACS first if it is not already available. Open HACS (shown as Marketplace in some installations), open its custom repositories menu, and add this address with category **Integration**. Until catalog acceptance, the repository must be added manually; the Marketplace button above is a shortcut:

`https://github.com/halilyildiz/vestel-akilli-yasam`

Install **Vestel Akıllı Yaşam**, follow any restart prompt, then open Settings → Devices & services → Add integration → **Vestel Akıllı Yaşam**. Sign in with the email/password from the mobile app and choose your existing home. There is no dependency on an older Vestel integration or a discovery helper.

[![Start setup](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vestel_appliances)

For a manual install, copy `custom_components/vestel_appliances` into your Home Assistant configuration directory and restart. If upgrading an existing manual installation of **this** integration, keep its config entry: the domain and unique IDs remain `vestel_appliances`, so entity preferences and references can be preserved.

## Updates and entities

- Supported devices added to the selected app home are discovered on the next successful poll, normally within 45 seconds. New entities do not require a reload.
- MQTT events request a fresh cloud reading. If live updates fail, polling continues. Subscription sessions refresh when the device set changes.
- Appliance controls and live updates start before the optional energy history fetch. Energy data loads in the background; missing history does not block controls. The initial fetch is cancelled when the integration entry is unloaded.
- Firmware/model revision changes cause discovery definitions to be refreshed. A malformed model must not prevent other appliances from working.
- Primary operating state, remaining time, warnings and controls are enabled. Technical diagnostics and estimated daily/monthly energy, water and cost sensors are disabled by default. Estimates are not meter measurements.
- Selected-program sensors remain available because program selection controls can become unavailable while a cycle is running.
- Removed devices are retained as unavailable instead of deleting their registry entries automatically.
- Temporary authentication-server failures and rate limits are treated as connection errors. Malformed responses are rejected before cached credentials are changed. Genuine account/token rejection can still require signing in again.

## Actions

The integration provides `vestel_appliances.apply`, `get_consumption`, `get_billing_settings`, `set_bill_limit`, `set_energy_price`, `set_subscriber_type`, `set_tariff_type` and `set_energy_management`. Their fields are available in the Home Assistant action editor. Appliance actions validate discovery limits and current state; there is no unrestricted raw-command action.

A cloud acknowledgement is followed by a readback. A delayed confirmation is not reported as a successful physical operation and does not trigger an automatic command replay. Billing settings modify the cloud account; consumption values are estimates.

For shared registers, readback compares the requested bit fields, including incompatible options automatically cleared by the change. An unrelated setting changing at the same time does not prevent confirmation. A multi-setting request can still partially apply if a later cloud write fails; check the resulting device state before trying again.

### Action examples

Replace `YOUR_HA_DEVICE_ID` with the **Home Assistant device registry ID** selected by the action editor, not an entity ID, cloud UUID or serial number. Prefer the regular entity controls for everyday use. Advanced `apply` keys and values must exist in your appliance's discovery description; the refrigerator example below is model dependent.

Turn off a supported refrigerator's screen saver:

```yaml
action: vestel_appliances.apply
data:
  device_id: YOUR_HA_DEVICE_ID
  updates:
    - key: Refrigeration.Refrigerator.Setting.ScreenSaver
      value: 0
```

Supply either `updates` or a full discovery `command` key in a call, never both. `updates` values are integers from that model's definition, not display labels or raw register strings.

Read three months of estimated consumption in a script. The read-only actions `get_consumption` and `get_billing_settings` require a response variable in scripts/automations:

```yaml
sequence:
  - action: vestel_appliances.get_consumption
    data:
      device_id: YOUR_HA_DEVICE_ID
      period: month
      count: 3
    response_variable: consumption
```

`period` accepts `day`, `week` or `month`; `count` accepts 1–366. The response contains `estimated`, `period` and dated `samples`. Missing values are unknown, not zero.

Set the app's estimated bill limit for the **entire home containing the selected device**:

```yaml
action: vestel_appliances.set_bill_limit
data:
  device_id: YOUR_HA_DEVICE_ID
  scope: home
  amount: 1000
  enabled: true
```

`scope: device` changes only the selected device's limit and is the default. The amount is a whole number from 0 to 2147483647 in the app's billing context. `set_energy_price`, `set_subscriber_type`, `set_tariff_type` and `set_energy_management` also affect the selected device's **home**, not just that appliance. These actions change Vestel's estimate settings, not your electricity supplier contract, and do not act as a physical power cutoff.

## Troubleshooting and privacy

| Symptom | What to check |
| --- | --- |
| Cannot connect, rate limit or temporary server error | Check internet access and the official app. Allow the regular polling cycle to retry; repeatedly signing in may increase rate limiting. |
| Invalid authentication / sign-in requested | Verify the account in the official app, then complete Home Assistant's reauthentication flow. |
| Appliance is missing or unavailable | Confirm the selected app home, supported device family, connection and panel remote-control permission. Check Repairs for incompatible descriptions. |
| An option is unavailable while running | The selected program, phase, mode or remote-control state may prohibit it. Check the official app and panel. |
| Command accepted but not confirmed | Check actual device state and the official app before retrying. Do not build an automatic retry loop around this message. |
| Consumption sensors are missing or empty | Enable the optional entities in the entity settings and allow the background history query to finish. Missing estimates do not indicate a control failure. |

Check connectivity and remote-control permission in the official app first. For an unsupported type or model description, look under Settings → System → Repairs. Download the integration's redacted diagnostics before reporting a bug, and inspect the file yourself before attaching it. Do not post account passwords, tokens, unredacted captures, MAC addresses or serial numbers.

Diagnostics retain selected technical metadata (model, firmware, device type and connection flags), capability definitions, register status, compatibility notices and command confirmation results. Unknown metadata fields are excluded. Known private fields and repeated sensitive values are masked, including nested data and embedded JSON. This is a best-effort filter: inspect the result because future cloud fields may contain personal information.

Email, password and refresh tokens are stored through Home Assistant's config-entry mechanism; the password is retained for login when refresh-token renewal is rejected. They are not protected by a separate integration-specific encryption layer. Protect your configuration files and backups as credentials. Diagnostics use known credential values for masking but do not export the config entry itself.

The integration does not send credentials to this repository or its maintainer. Authentication goes to the cloud provider; there is no direct local-only control mode. Cloud API changes can break the integration. See [SECURITY.md](SECURITY.md) for vulnerability reporting; ordinary, non-sensitive bugs belong in [Issues](https://github.com/halilyildiz/vestel-akilli-yasam/issues).

## Development and validation

```sh
python -m unittest discover -s tests -v
```

The offline suite currently has 145 tests covering protocol constraints, authentication error classification, response validation, command readback, background startup, energy isolation and diagnostic redaction. It uses protocol descriptions with synthetic appliance metadata and register examples; it makes no appliance or cloud calls. Most HA modules are test doubles, so this suite is not a substitute for Home Assistant runtime testing. The maintainer has reported testing four household appliances; model and firmware details are not yet published as a compatibility matrix. Other physical models are not certified by these tests.

GitHub Actions runs the offline tests, Home Assistant hassfest and HACS validation. Catalog acceptance is a separate review by its maintainers and must not be inferred from a successful custom-repository install.

## Uninstall

Remove the integration entry from Settings → Devices & services, then uninstall its repository through Marketplace and follow the restart prompt. Removing an entry also removes its Home Assistant entities; automations referring to them need updating. Your appliance pairings in the official app are separate.

## License and acknowledgements

Code is released under the [MIT license](LICENSE). See [third-party notices](NOTICE.md) for upstream acknowledgements and the separate status of the Vestel application artwork.
