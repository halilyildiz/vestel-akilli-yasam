# Changelog

## 0.3.0 — 2026-11-23

[English / Türkçe release notes](docs/releases/0.3.0.md)

### Upgrade notes

- Select options, enum sensor states and climate fan modes now use stable machine tokens instead of translated display strings. Update automations, scripts, templates and dashboards that depend on literal values; for example, `Ekonomi` becomes `eco`, `Pamuklu` becomes `cotton`, and fan mode `Auto` becomes `auto`.
- The integration domain `vestel_appliances`, existing unique IDs and entity registry entries are preserved. Default entry titles change to **Vestel Smart Life**; custom entry titles are retained. Existing entity IDs are not renamed.
- The repository is now `halilyildiz/vestel-smart-life-home-assistant`. Use the new repository address for new installations. Migrating from Mehmet Aktaş's `vestel_smarthome` integration is a separate setup, not an automatic upgrade.
- See the [English](docs/upgrading.md) or [Turkish](docs/upgrading.tr.md) migration guide before upgrading. The Home Assistant minimum remains **2026.11.0**.

### Changed

- Add native English/Turkish translations for entity names, option/state labels, services, selectors and user-facing errors. Use English as the source language.
- Rename the displayed integration to **Vestel Smart Life** and update repository links and HACS shortcuts.
- Load optional energy history in a config-entry background task after appliance platforms and live updates start. Cancel the initial history fetch on unload.

### Fixed

- Treat temporary Cognito failures and rate limits, including HTTP 400 throttling responses, as connection errors rather than rejected credentials.
- Validate authentication results, token lifetimes and nested device/billing response shapes before using them. Do not partially replace cached credentials with malformed data.
- Confirm only targeted register bit fields, including automatically cleared incompatible options, so unrelated changes do not prevent readback confirmation. Preserve full-register checks where no bit layout exists and the UV/cancellation result checks.
- Restrict diagnostic metadata to known technical scalar fields and improve masking of nested and repeated private values. Diagnostics must still be reviewed before sharing.
- Update checkout/setup-python actions to Node.js 24 runtimes.

### Documentation and attribution

- Reorganize English/Turkish READMEs around installation and first use, with separate advanced-action, migration, troubleshooting and development guides.
- Expand credential-storage explanations and private security reporting instructions.
- Explicitly credit Mehmet Aktaş's MIT-licensed source project and include both complete MIT notices and third-party notices in the installable integration folder.

### Validation

- Expand the offline suite from 103 to 155 tests. Home Assistant classes are mostly test doubles; these tests do not certify every physical appliance or a real Home Assistant runtime.
- Keep the existing hassfest and HACS validation workflow. New linting, dependency vulnerability scanning and automated dependency maintenance are deferred to a later release.

## 0.2.1

- Prepare the existing 0.2.0 integration for Marketplace/custom-repository distribution.
- Add repository metadata, complete English/Turkish setup text, installation documentation, attribution and validation workflows.
- Replace captured test state and household metadata with synthetic examples. No appliance control behavior changes.

## 0.2.0

- Discover new supported appliances and add their entities without reloading.
- Refresh model descriptions after firmware/model revision changes.
- Refresh MQTT subscription sessions when appliances are added or removed.
- Report unsupported families and isolate incompatible descriptions through Repairs.
- Preserve existing entity IDs, disabled defaults and user registry preferences.
- Protect fault attributes when a device is removed from the account.
