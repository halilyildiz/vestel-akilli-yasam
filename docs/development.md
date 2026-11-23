# Development and runtime behavior

[Home](../README.md) · [Türkçe](development.tr.md)

## Runtime behavior

- Supported devices added to the selected app home are discovered on the next successful poll, normally within 45 seconds. New entities do not require a reload.
- MQTT events request a fresh cloud reading. If live updates fail, polling continues. Subscription sessions refresh when the device set changes.
- Appliance controls and live updates start before the optional energy history fetch. Energy data loads in the background; missing history does not block controls. The initial fetch is cancelled when the integration entry is unloaded.
- Firmware/model revision changes cause discovery definitions to be refreshed. A malformed model must not prevent other appliances from working.
- Primary operating state, remaining time, warnings and controls are enabled. Technical diagnostics and estimated daily/monthly energy, water and cost sensors are disabled by default. Estimates are not meter measurements.
- Selected-program sensors remain available because program selection controls can become unavailable while a cycle is running.
- Removed devices are retained as unavailable instead of deleting their registry entries automatically.
- Temporary authentication-server failures and rate limits are treated as connection errors. Malformed responses are rejected before cached credentials are changed. Genuine account/token rejection can still require signing in again.

## Validation

```sh
python -m unittest discover -s tests -v
```

The offline suite currently has 155 tests covering protocol constraints, authentication error classification, response validation, command readback, background startup, energy isolation and diagnostic redaction. It uses protocol descriptions with synthetic appliance metadata and register examples; it makes no appliance or cloud calls. Most HA modules are test doubles, so this suite is not a substitute for Home Assistant runtime testing. The maintainer has reported testing four household appliances; model and firmware details are not yet published as a compatibility matrix. Other physical models are not certified by these tests.

GitHub Actions runs the offline tests, Home Assistant hassfest and HACS validation. Catalog acceptance is a separate review by its maintainers and must not be inferred from a successful custom-repository install.
