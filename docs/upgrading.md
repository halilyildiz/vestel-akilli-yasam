# Updating and migrating

[Home](../README.md) · [Türkçe](upgrading.tr.md)

The integration is displayed as **Vestel Smart Life**. The connected vendor app/account is **Vestel Akıllı Yaşam / Smart Life (homevsmart)**; this is **not Tuya Smart Life**. Vestel-manufactured appliances sold abroad or under other brands are compatible only if they use the supported account, cloud and legacy protocol. Other account regions and models require verification.

English is the source language, with Turkish translations for setup, entity names, option/state labels, action descriptions and user-facing errors. Home Assistant uses its language settings to display the supported translations. Unknown model fields fall back to readable technical names.

The integration domain remains `vestel_appliances`; existing unique IDs and entity registry entries are preserved. Default integration entry titles are updated, while custom entry titles are retained. Existing entity IDs are not renamed by this change. The current repository address remains `halilyildiz/vestel-akilli-yasam`. A repository rename is planned; use the working address in the installation guide until it is completed.

**Automation migration:** select options, enum sensor states and climate fan modes now use stable machine tokens rather than translated text. Home Assistant translates their displayed labels. Before upgrading, review automations, scripts, templates and dashboards that compare literal states or pass option/fan-mode strings. Check the actual tokens in Developer Tools → States, rather than copying translated display labels.

| Previous value | Machine token | English display | Turkish display |
| --- | --- | --- | --- |
| `Ekonomi` | `eco` | Economy | Ekonomi |
| `Pamuklu` | `cotton` | Cotton | Pamuklu |
| `Soğutma` | `cooling` | Cooling | Soğutma |
| `Auto` (climate fan mode) | `auto` | Automatic | Otomatik |

The values of the advanced `vestel_appliances.apply` action remain vendor-defined integer codes; do not substitute these state tokens for its `updates[].value` field. State history may contain both the old text and new tokens across this upgrade.

## Updating this integration

Back up Home Assistant before upgrading. Update the package through HACS and follow its restart prompt. Keep the existing `vestel_appliances` config entry; removing and adding it again is not required. For a manual installation, replace the contents of `custom_components/vestel_appliances` with the new release, including `LICENSE` and `NOTICE.md`, and restart.

Review scripts and automations that use literal select/enum/fan states using the table above. Entity IDs are retained, but preserving IDs does not preserve old option strings. Recheck affected automations before relying on them. Restore your previous package version and configuration backup if you need to roll back; this project does not automatically rewrite your automations or recorded history.

## Coming from Mehmet Aktaş's integration

The original integration uses `vestel_smarthome`; this project uses `vestel_appliances`. They are separate integrations. Installing this project does not migrate the original config entry, entity IDs, dashboards or automations automatically.

Record the old entity IDs and dependent automations, install this integration, sign in and select the same home, then check the new entities and update references. Avoid leaving duplicate automations active for the same appliance during the transition. Remove the old entry only after verifying the replacement. Vendor-app appliance pairings are separate from Home Assistant entries.
