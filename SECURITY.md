# Security policy and reporting

## Reporting a vulnerability

Do not post vulnerability details, credentials, tokens, signed URLs, device identifiers or unredacted diagnostics in public issues.

If private vulnerability reporting is enabled, use [GitHub's private report form](https://github.com/halilyildiz/vestel-akilli-yasam/security/advisories/new). If the form is unavailable, open a non-sensitive issue titled **Private security contact requested** asking the maintainer for a private channel. Do not include the vulnerability details or attachments until a private channel is established.

In the private report, include:

- Integration version or commit, Home Assistant version and affected device family.
- Minimal reproduction steps, expected behavior, observed behavior and potential impact.
- Sanitized examples using synthetic credentials and device identifiers where possible.

Do not send real account passwords, refresh tokens or AWS session credentials, even in a private report. If a diagnostic file is needed, inspect and redact it before sharing. Never test against another person's account or appliances.

This community project has no published guaranteed response or remediation time. If you do not receive a response, follow up through the same private channel without adding sensitive details to a public issue.

## Versions and advisories

Report the exact installed release and, if relevant, whether the issue also affects `main`. The current README describes `main`, which can contain changes not yet released. No security backport policy for older releases is currently published.

Check [releases](https://github.com/halilyildiz/vestel-akilli-yasam/releases), [CHANGELOG.md](CHANGELOG.md) and published [security advisories](https://github.com/halilyildiz/vestel-akilli-yasam/security/advisories) for available fixes. A passing HACS or hassfest check is not a security certification. This document is a reporting policy, not an audit report.

## Credentials and cloud access

The integration authenticates to the existing Vestel/homevsmart account using HTTPS and subscribes to AWS IoT using temporary credentials over TLS. It does not create users or change cloud authorization policies. Its MQTT transport is used for status subscriptions; appliance commands use the REST API. Account access and remote operations remain subject to the vendor's authorization and appliance requirements.

Email, password and refresh tokens are stored through Home Assistant's config-entry mechanism. The password remains available for login if refresh-token renewal is rejected. There is no additional integration-specific encryption layer. Restrict access to the Home Assistant configuration and protect backups. Credentials are sent to the cloud provider, not to this repository or its maintainer.

Public application client configuration in the transport code is separate from an individual user's password, tokens and temporary AWS credentials. It must not be treated as a secret authorization boundary. If you suspect a vendor-side authorization issue, avoid posting live endpoints with credentials or exploit details in public.

## Diagnostic data

Diagnostics export selected technical metadata, capability definitions, register status, compatibility notices, live-connection statistics and command confirmation results. Unknown metadata fields are excluded. Known sensitive fields, nested values, embedded JSON and repeated known private strings are masked. Config-entry credentials are used only as masking inputs, not exported as a config-entry dump.

Redaction is best effort and cannot establish that every future vendor field is safe to share. Inspect the output before attaching it anywhere. Diagnostic register values can reveal appliance operating state even when account and device identifiers are removed.

## If credentials were exposed

Remove public attachments or logs that contain secrets, change the affected account password and use the provider's session/token revocation options if available. Changing a password alone should not be assumed to invalidate every existing token. Reauthenticate the integration as needed, and protect or replace exposed configuration backups. Do not reproduce the leaked values in a public follow-up.
