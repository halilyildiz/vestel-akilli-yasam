# Device families and protocol evidence

This development branch expands legacy-register discovery from four to eight
families. It is not a claim that all devices in the Vestel app are compatible.
The new families have **no physical-device verification**.

| Family | This branch | APK evidence |
| --- | --- | --- |
| AC, WD, DW, RF | Existing controls | Existing integration coverage |
| WM — standalone washer | Experimental controls | `demo_wm_t225`, `demo_wm_t33t`, `demo_wm_ic`; `WMFORPR`, `WMDCPST`, `WMDOORS` |
| FD — French-door refrigerator | Experimental discovery-defined zone/mode controls | `demo_fd`; FD register mappers |
| TD — tumble dryer | Monitoring only | `demo_td`; `TDDCPST`, `TDREMTC`, `TDREMTI`; start and packed program semantics need resolution |
| OV — oven | Monitoring only | `demo_ov`; `OVGENMO`, `OVPROSE`, `OVTEMSE`; ambiguous chef commands and program-specific temperature rules need an adapter |

WM uses its own discovery values rather than WD program numbers. Remote control
must be enabled, program selection is limited to selection states, and supported
states/phases and included options are enforced. FD uses its own zone definitions;
RF door meanings are not applied to FD. The diagnostics report each device's
`support_level`. Technical entities retain the existing disabled-by-default policy.

TD and OV expose only validated `status` and `errors` definitions. Controls are
absent from all six control platforms and writes are rejected at the coordinator
and protocol layers, including the generic `apply` service. No raw-register escape
hatch or synthetic start/pause opcode is added. Unknown boolean meanings remain
unknown; only the two TD status fields explicitly compared to 1 in the APK mapper
receive that missing comparison value. No vendor response is modified in place.
New numeric readings outside their discovery limits are unavailable. In
particular, FD negative-temperature encodings are not guessed from large unsigned
register values. Explicit, unscaled Celsius/minute schema units are used for HA
sensor metadata; signed/offset encodings still require a matching decoder.

## Services extracted from APK 3.2413.29

Read from Retrofit annotations and call/data mappers in the user-provided APK.
Paths below are relative to the vendor's API base; they do not include account
IDs or credentials. The APK and its full demo assets are not redistributed.

| Route | Purpose / source | Implemented here |
| --- | --- | --- |
| `GET /v1.0/homes/{homeId}/devices` | `HomesApi.c`, `GetDevicesResponseNetworkDTO.Items` | Legacy appliance discovery; counts of other returned collections in diagnostics |
| `GET /v1.0/device/discovery?uuid=…` | Existing legacy capability discovery | Validated register schema, including new families |
| `GET /v1.0/homeappliances/legacy/status?uuid=…` | Existing legacy status | Register decoding |
| `POST /v1.0/customer/devices/{uuid}/legacy/command` | Existing legacy command route | Existing and experimental writable families only |
| `GET /v1.0/appliances/{uuid}/status` | `SendNewJsonCommandApi.a` | Not implemented; property/value JSON needs its own decoder |
| `POST /v1.0/appliances/{uuid}/command` | `SendNewJsonCommandApi.b` | Not implemented; separate request DTO and readback semantics |
| `GET /v1.0/homeappliances/{uuid}/status/all` | `HCAApi.a` | Not implemented; component-based state |
| `POST /v1.0/customer/devices/{uuid}/command` | `HCAApi.c` | Not implemented; component/program/option DTO |
| `GET /v1.0/appliances/{uuid}/discovery` | `LockDeviceApi.b` | Not implemented; lock-specific schema |

The home response has separate `homeappliances`, `nonSmartDevices`, `televisions`,
`pairedDevices`, `partnerDevices`, `chargers`, and `thirdpartyDevices` collections.
`Api.devices()` never concatenates these into the legacy register pipeline.
Diagnostics retain counts only, without third-party IDs or login data.

`CloudSignInRepositoryImpl` separately injects a `TuyaInteractor` and
`DreameSdkWrapper` and has separate sign-in/home-binding operations. Therefore a
successful Vestel login is not proof that third-party devices can use the legacy
transport. Device icons are not evidence of a compatible command format.

## Remaining work

1. Resolve TD `TDSTART` value 2 in the demo versus value 1 in the old domain mapper;
   determine the applicable protocol/model revision. `TDSELPR` also packs an 8-bit
   program and a 2-bit value in the old mapper, which a whole-register write could
   overwrite. Confirm resulting status fields before adding lifecycle controls.
2. Add an OV adapter for `Config`/`Running`/`Stopped`, standby, remote-control
   prerequisites, per-program `availableTemperatures`, and chef session commands.
   The demo contains two `Cooking.Oven.Command.Process` definitions with different
   registers and request-value commands that cannot be represented as buttons.
3. Implement separate JSON/HCA transport adapters with fixture-based status,
   constraint and command/readback contracts. Do not retry writes on uncertainty.
4. Add Tuya/Dreame account/home adapters and native HA platforms for their devices.
   Determine which models/providers are returned instead of assuming every product
   category uses a particular SDK. TVs/chargers/locks likewise need their own
   discovery and platform mappings. Standalone freezer support must be tied to
   the actual returned family/schema; the app's freezer icon is insufficient.
5. Mark model reports as physical verification only when independently confirmed;
   offline demo validation and synthetic tests are separate evidence levels.

## Offline evidence

APK base SHA-256:
`7e5a1555e3adb191c029138da104140a3e9ee8fbf970ffc4638993c8c35b005d`.

All six local demo descriptions listed above passed discovery preparation and
entity creation/property access across the eight existing HA platforms using the
test runtime and synthetic register values. This is not a live cloud test, a
physical appliance test, or validation of every mode/option combination. Public
tests use minimal synthetic protocol examples rather than copying APK assets.
