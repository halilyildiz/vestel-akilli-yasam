# Advanced actions

[Home](../README.md) · [Türkçe](advanced.tr.md)

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
