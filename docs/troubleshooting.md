# Troubleshooting and privacy

[Home](../README.md) · [Türkçe](troubleshooting.tr.md)

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

The integration does not send credentials to this repository or its maintainer. Authentication goes to the cloud provider; there is no direct local-only control mode. Cloud API changes can break the integration. See [SECURITY.md](../SECURITY.md) for vulnerability reporting; ordinary, non-sensitive bugs belong in [Issues](https://github.com/halilyildiz/vestel-akilli-yasam/issues).

## Uninstall

Remove the integration entry from Settings → Devices & services, then uninstall its repository through Marketplace and follow the restart prompt. Removing an entry also removes its Home Assistant entities; automations referring to them need updating. Your appliance pairings in the official app are separate.
