"""Real discovery fixtures; all command tests are offline, no network."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components/vestel_appliances"
for name, path in (("custom_components", ROOT / "custom_components"), ("custom_components.vestel_appliances", PKG)):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module

from custom_components.vestel_appliances.protocol import Device
from custom_components.vestel_appliances.fields import SchemaError

FIXTURE = ROOT / "tests/fixtures/device-snapshot.json"


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        capture = json.loads(FIXTURE.read_text())
        self.states = {d["metadata"]["deviceType"]: Device(d["metadata"], d["discovery"], d["registers"])
                       for d in capture["devices"]}
        # Fixture was captured while WD was in standby. Successful live writes
        # were observed after it woke; use that state for normal command tests.
        self.states["WD"].registers["WDDOORS"] = "00007"

    def field(self, family, suffix):
        return self.states[family].find_suffix(suffix, "settings", "options", "commands", "programs", "status")

    def build(self, family, suffix, value):
        return self.states[family].build([(self.field(family, suffix)["key"], value)])

    def test_screen_saver_confirmed_read_and_both_command_directions(self):
        rf = self.states["RF"]
        self.assertTrue(rf.decode(self.field("RF", ".Setting.ScreenSaver")))
        self.assertEqual(self.build("RF", ".Setting.ScreenSaver", 0), ["RFSSAVE00000"])
        self.assertEqual(self.build("RF", ".Setting.ScreenSaver", 1), ["RFSSAVE00001"])

    def test_freezer_keeps_cooler(self):
        self.assertEqual(self.build("RF", ".Freezer.Temperature", 20), ["RFTEMSE01044"])

    def test_refrigerator_aggregate_door_follows_apk(self):
        rf = self.states["RF"]
        for value in range(4):
            rf.registers["RFDOORA"] = f"{value:05d}"
            self.assertEqual(rf.refrigerator_door_open(), value != 3)

    def test_unknown_refrigerator_door_code_is_not_guessed(self):
        rf = self.states["RF"]
        rf.registers["RFDOORA"] = "00004"
        self.assertIsNone(rf.refrigerator_door_open())
        rf.registers.pop("RFDOORA")
        self.assertIsNone(rf.refrigerator_door_open())

    def test_cooler_keeps_freezer(self):
        self.assertEqual(self.build("RF", ".Cooler.Temperature", 5), ["RFTEMSE01298"])

    def test_unknown_enum_value_rejected(self):
        with self.assertRaises(SchemaError): self.build("RF", ".Cooler.Temperature", 3)

    def test_wd_program_specific_temperature(self):
        # Current Hızlı Yıka & Kurut permits Cold/30 C, not 90 C.
        self.assertEqual(self.build("WD", ".Option.Temperature", 2), ["WDUISET01794"])
        with self.assertRaises(SchemaError): self.build("WD", ".Option.Temperature", 8)

    def test_wd_remote_disabled_blocks_writes(self):
        self.states["WD"].registers["WDDOORS"] = "00019"
        with self.assertRaises(SchemaError): self.build("WD", ".Option.Temperature", 2)

    def test_wd_idle_stale_phase_does_not_block_temperature(self):
        self.assertEqual(self.build("WD", ".Option.Temperature", 2), ["WDUISET01794"])

    def test_wd_running_phase_blocks_late_temperature_change(self):
        self.states["WD"].registers["WDDCPST"] = "00001"
        with self.assertRaises(SchemaError): self.build("WD", ".Option.Temperature", 2)

    def test_dw_running_program_cannot_be_reselected(self):
        with self.assertRaises(SchemaError): self.build("DW", ".Program.Eco50", 4)

    def test_dw_program_select_when_idle(self):
        self.states["DW"].registers["DWPROST"] = "00000"
        self.assertEqual(self.build("DW", ".Program.Eco50", 4), ["DWPROSI00004"])

    def test_program_key_cannot_send_arbitrary_numeric_command(self):
        with self.assertRaises(SchemaError): self.build("WD", ".Program.Cotton", 9999)

    def test_status_field_cannot_be_written(self):
        with self.assertRaises(SchemaError): self.build("WD", ".Status.ExecutionState", 6)

    def test_command_cannot_be_injected_as_an_update(self):
        with self.assertRaises(SchemaError): self.build("WD", ".Command.Start", 6)

    def test_only_defined_command_values_are_generated(self):
        d = self.field("WD", ".Command.Start")
        self.assertEqual(self.states["WD"].command(d["key"]), "WDDCPST00001")

    def test_uv_command_opcode_is_separate_from_named_status(self):
        dw = self.states["DW"]
        for name, sent, expected in (("UvonOn", "DWSETTS00012", 112), ("UvonOff", "DWSETTS00112", 12)):
            key = "Dishcare.DishWasher.Command." + name
            self.assertEqual(dw.command(key), sent)
            self.assertEqual(dw.expected_registers([sent], command=key), {"DWSETTS": expected})

    def test_uv_without_matching_status_definition_is_blocked(self):
        dw = self.states["DW"]
        status = dw.find_suffix(".Status.SettingIndex", "status")
        status["values"] = []
        with self.assertRaises(SchemaError): dw.command("Dishcare.DishWasher.Command.UvonOn")

    def test_dw_delay_matches_official_app_hour_minute_mapper(self):
        # APK HourMinuteToDWDefaultDelayDomain returns DWDelayDurationDomain,
        # which DWCloudDomainToCloudEntity writes to DWDELDU in minutes.
        self.states["DW"].registers["DWPROST"] = "00000"
        self.assertEqual(self.build("DW", ".Option.DelayTimer", 60), ["DWDELDU00060"])
        self.assertEqual(self.build("DW", ".Option.DelayTimer", 0), ["DWDELDU00000"])

    def test_dw_dry_hygiene_exclusion_preserves_unrelated_options(self):
        dw = self.states["DW"]
        dw.registers.update(DWPROST="00000", DWPROSI="00004", DWPROOP=str((1 << 10) | (1 << 1)))
        self.assertEqual(self.build("DW", ".Option.ExtraDry", 1), ["DWPROOP00514"])
        dw.registers["DWPROOP"] = str((1 << 9) | (1 << 8))
        self.assertEqual(self.build("DW", ".Option.ExtraHygiene", 1), ["DWPROOP01280"])

    def test_dw_delay_rejects_non_hour_steps_and_out_of_range(self):
        self.states["DW"].registers["DWPROST"] = "00000"
        for value in (30, -60, 1500):
            with self.subTest(value=value), self.assertRaises(SchemaError):
                self.build("DW", ".Option.DelayTimer", value)

    def test_ac_dry_disallows_eco(self):
        with self.assertRaises(SchemaError): self.build("AC", ".Fan.Eco", 1)

    def test_ac_turbo_clears_only_incompatible_bits(self):
        ac = self.states["AC"]
        ac.registers["ACGENSI"] = "00001"
        ac.registers["ACFANPO"] = str(512 | 128 | 256 | 2 | 48)
        self.assertEqual(self.build("AC", ".Fan.Turbo", 1), ["ACFANPO00307"])

    def test_ac_temperature_keeps_auto_on_sentinel(self):
        self.assertEqual(self.build("AC", ".Setting.Temperature", 24), ["ACTEMOT32760"])

    def test_ac_temp_limits_follow_eco(self):
        ac = self.states["AC"]
        ac.registers["ACGENSI"] = "00001"
        ac.registers["ACFANPO"] = "00562"
        with self.assertRaises(SchemaError): self.build("AC", ".Setting.Temperature", 22)

    def test_auto_on_cancel_correctly_handles_pre_shifted_sentinel(self):
        d = self.field("AC", ".Command.AutoOn.Cancel")
        self.assertEqual(self.states["AC"].command(d["key"]), "ACTEMOT32759")

    def test_combined_time_update_is_one_command(self):
        ac = self.states["AC"]
        hour = self.field("AC", ".Setting.AutoOff.Hour")["key"]
        minute = self.field("AC", ".Setting.AutoOff.Minute")["key"]
        self.assertEqual(ac.build([(hour, 14), (minute, 18)]), ["ACOFFTV00590"])

    def test_missing_shared_register_never_defaults_to_zero(self):
        self.states["RF"].registers.pop("RFTEMSE")
        with self.assertRaises(SchemaError): self.build("RF", ".Cooler.Temperature", 4)

    def test_quick_off_thirty_minutes_matches_official_app_range(self):
        hour = self.field("AC", ".Setting.QuickOffTime.Hour")["key"]
        minute = self.field("AC", ".Setting.QuickOffTime.Minute")["key"]
        self.assertEqual(self.states["AC"].build([(hour, 0), (minute, 30)]), ["ACQOFFT00960"])

    def test_pause_cannot_be_sent_to_idle_washer(self):
        d = self.field("WD", ".Command.Pause")
        with self.assertRaises(SchemaError): self.states["WD"].command(d["key"])

    def test_time_dry_does_not_enable_two_drying_methods(self):
        with self.assertRaises(SchemaError): self.build("WD", ".Option.TimeDry", 1)

    def test_wd_standby_blocks_program_selection(self):
        self.states["WD"].registers["WDDOORS"] = "00023"
        with self.assertRaises(SchemaError): self.build("WD", ".Program.Cotton", 2)

    def test_dw_end_requires_acknowledgement_before_program_selection(self):
        self.states["DW"].registers["DWPROST"] = "00003"
        with self.assertRaises(SchemaError): self.build("DW", ".Program.Eco50", 4)

    def test_dw_end_can_be_acknowledged_with_named_command(self):
        self.states["DW"].registers["DWPROST"] = "00003"
        d = self.field("DW", ".Command.PreProgram")
        self.assertEqual(self.states["DW"].command(d["key"]), "DWPROST00000")


if __name__ == "__main__": unittest.main()
