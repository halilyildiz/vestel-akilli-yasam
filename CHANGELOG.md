# Changelog

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
