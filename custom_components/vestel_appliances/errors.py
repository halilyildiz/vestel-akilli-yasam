"""Stable error keys with English fallbacks and Home Assistant translations."""
from .const import DOMAIN


DEFAULT_MESSAGES = {'amount_invalid': 'Enter a finite amount of zero or greater.',
 'monitoring_only': 'This appliance family currently supports monitoring only; no command was sent.',
 'auth_connection_failed': 'Could not reach the Vestel authentication server.',
 'auth_expiry_invalid': 'Invalid Vestel session lifetime.',
 'auth_rejected_http': 'The Vestel session could not be renewed (HTTP {http_status}).',
 'auth_response_invalid': 'Unexpected Vestel authentication response format.',
 'auth_result_invalid': 'Could not read the Vestel authentication result.',
 'auth_server_http': 'The Vestel authentication server is temporarily unavailable (HTTP '
                     '{http_status}).',
 'auth_server_unavailable': 'The Vestel authentication server is temporarily unavailable.',
 'auth_token_invalid': 'The Vestel response contains no valid session token.',
 'billing_action_unsupported': 'Unsupported billing action.',
 'billing_option_unsupported': 'Unsupported billing setting.',
 'billing_settings_invalid': 'Could not read billing estimate settings.',
 'billing_unconfirmed': 'Setting sent, but readback has not confirmed it. It was not resent '
                        'automatically.',
 'billing_value_unsupported': 'Unsupported billing setting value.',
 'bit_layout_incomplete': 'Incomplete bit layout.',
 'bit_layout_invalid': 'Invalid bit layout.',
 'boolean_definition_missing': 'Boolean comparison has no definition.',
 'boolean_invalid': 'Invalid on/off value.',
 'cancel_in_progress': 'Cancellation/draining is already in progress; no command was resent.',
 'choose_change': 'Choose a setting or command.',
 'cloud_connection_failed': 'Could not get a response from the Vestel server.',
 'cloud_response_invalid': 'Unexpected Vestel response format.',
 'collection_failed': 'Could not read the Vestel appliance list. Check the integration connection.',
 'collection_invalid': 'Unexpected Vestel appliance list format.',
 'command_rejected': 'Vestel did not accept the command.',
 'command_unconfirmed': 'Command accepted, but the device has not confirmed it. Check its state; '
                        'it was not resent automatically.',
 'command_unsupported': 'Unsupported command.',
 'consumption_range_invalid': 'Invalid consumption query range.',
 'consumption_record_invalid': 'Consumption history contains an invalid record.',
 'consumption_response_invalid': 'Unexpected consumption history format.',
 'currency_invalid': 'Enter a three-letter currency code, for example TRY.',
 'device_not_found': 'Device not found.',
 'device_offline': 'The appliance is offline.',
 'devices_invalid': 'Could not read the Vestel appliance list.',
 'discovery_invalid': 'Could not read the appliance capability description.',
 'dry_conflict': 'Turn off the other drying type first; level and time cannot be selected '
                 'together.',
 'empty_status': 'Fresh device status is empty; no command was sent.',
 'encoded_value_invalid': 'The value does not fit the register bit field.',
 'fan_unavailable': 'Fan speed is unavailable in this mode.',
 'feature_unavailable': 'This feature is unavailable in the selected mode/program.',
 'home_id_invalid': 'Could not read the Vestel home ID.',
 'home_record_invalid': 'The Vestel home list contains an invalid record.',
 'homes_invalid': 'Could not read the Vestel home list.',
 'hvac_mode_unsupported': 'Unsupported air conditioner mode.',
 'identity_connection_failed': 'Could not reach the live-update identity server.',
 'identity_http': 'Could not obtain live-update credentials (HTTP {http_status}).',
 'identity_invalid': 'Invalid live-update identity.',
 'identity_operation_unsupported': 'Unsupported identity operation.',
 'identity_response_invalid': 'Invalid live-update identity response.',
 'incompatible_option': 'This option is incompatible with another setting.',
 'invalid_step': 'The requested value does not match the supported step.',
 'iot_credentials_incomplete': 'Temporary live-update credentials are incomplete.',
 'iot_credentials_missing': 'No temporary live-update credentials were returned.',
 'iot_expiry_invalid': 'Invalid temporary live-update credential lifetime.',
 'limit_enabled_invalid': 'The limit state must be on or off.',
 'live_topics_missing': 'No appliance channel was found for live updates.',
 'no_changes': 'There are no changes to send.',
 'not_ready_to_start': 'The appliance is already running or is not ready to start.',
 'not_running': 'A program that is not running cannot be paused.',
 'not_writable': 'This field is not a writable appliance setting.',
 'option_unavailable': 'This option is unavailable in the current mode/program.',
 'out_of_range': 'The requested value is outside the allowed range.',
 'program_not_found': 'Program not found.',
 'program_value_invalid': 'The program value does not match discovery.',
 'quick_off_range': 'Use 0 to cancel or 30–300 minutes in 30-minute steps.',
 'quota_device_missing': 'No bill-limit setting was found for this appliance.',
 'quota_invalid': 'The bill limit must be a whole number from 0 to 2147483647.',
 'readback_definition_missing': 'The field definition for readback is missing.',
 'readback_fields_missing': 'The command readback fields are incomplete.',
 'reauth_required': 'Sign in to your Vestel account again.',
 'refresh_token_invalid': 'Invalid Vestel refresh token.',
 'register_boolean': 'A boolean is not a register value.',
 'register_name_invalid': 'Invalid register name.',
 'register_range': 'Register is outside the 16-bit range.',
 'register_value_invalid': 'Missing or invalid register value.',
 'remote_required': 'Enable remote control on the appliance panel.',
 'request_http': 'The Vestel request failed (HTTP {http_status}).',
 'return_to_selection': 'First return to program selection from the end screen.',
 'separate_changes': 'Send commands and setting changes separately.',
 'session_rejected': 'The Vestel session was rejected.',
 'status_invalid': 'Could not read the appliance status.',
 'status_unavailable': 'Fresh appliance status could not be read.',
 'temperature_offset_missing': 'Temperature offset is missing.',
 'unsupported_phase': 'This option cannot be changed in the current program phase.',
 'uv_result_missing': 'The discovery description has no result state for this UV command.',
 'value_unavailable': 'This value is unsupported for the selected program/mode.',
 'vestel_device_not_found': 'Vestel device not found.',
 'wake_appliance': 'The appliance is in standby; wake it from the panel or Vestel app.',
 'whole_degree_required': 'Enter a whole degree.',
 'whole_number_required': 'Enter a whole number.'}


class LocalizedError(Exception):
    def __init__(self, key, *, placeholders=None):
        self.translation_key = key if key in DEFAULT_MESSAGES else None
        self.translation_placeholders = placeholders or {}
        message = DEFAULT_MESSAGES.get(key, key)
        super().__init__(message.format(**self.translation_placeholders) if self.translation_key else message)


def user_error(error, *, error_type=None):
    """Translate at the HA boundary, retaining readable fallback messages."""
    if error_type is None:
        from homeassistant.exceptions import HomeAssistantError
        error_type = HomeAssistantError
    if isinstance(error, str):
        error = LocalizedError(error)
    key = getattr(error, "translation_key", None)
    if key is None:
        return error_type(str(error))
    return error_type(str(error), translation_domain=DOMAIN, translation_key=key,
                      translation_placeholders=error.translation_placeholders)
