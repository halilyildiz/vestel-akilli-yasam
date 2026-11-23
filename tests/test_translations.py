"""Native translation coverage, stable identities and canonical state tokens."""
import ast
import importlib
import json
from pathlib import Path
import re
import sys
import types
from enum import IntFlag, StrEnum
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import test_coordinator  # noqa: F401 -- shared minimal HA runtime
import test_entity_descriptions  # noqa: F401 -- entity metadata stubs
from custom_components.vestel_appliances.const import APP_NAME, DOMAIN, choice, translation_key
from custom_components.vestel_appliances.errors import DEFAULT_MESSAGES, user_error
from custom_components.vestel_appliances.fields import SchemaError
from custom_components.vestel_appliances.protocol import Device

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / 'custom_components/vestel_appliances'


def shape(value):
    if isinstance(value, dict):
        return {key: shape(child) for key, child in value.items()}
    return None


class TranslationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        class Features(IntFlag):
            TARGET_TEMPERATURE = 1
            FAN_MODE = 2
            TURN_ON = 4
            TURN_OFF = 8

        class Modes(StrEnum):
            AUTO = 'auto'
            COOL = 'cool'
            HEAT = 'heat'
            DRY = 'dry'
            FAN_ONLY = 'fan_only'
            OFF = 'off'

        modules = {}
        for platform, entity in [('climate', 'ClimateEntity'), ('select', 'SelectEntity'),
                                 ('switch', 'SwitchEntity'), ('number', 'NumberEntity'),
                                 ('time', 'TimeEntity'), ('button', 'ButtonEntity')]:
            module = types.ModuleType('homeassistant.components.' + platform)
            setattr(module, entity, type(entity, (test_entity_descriptions.Entity,), {}))
            modules[module.__name__] = module
        modules['homeassistant.components.climate'].ClimateEntityFeature = Features
        modules['homeassistant.components.climate'].HVACMode = Modes
        modules['homeassistant.components.number'].NumberMode = SimpleNamespace(BOX='box')
        self.enterContext(patch.dict(sys.modules, modules))
        self.enterContext(patch.object(sys.modules['homeassistant.const'], 'ATTR_TEMPERATURE', 'temperature', create=True))
        self.catalogs = {language: json.loads((COMPONENT / 'translations' / f'{language}.json').read_text())
                         for language in ('en', 'tr')}
        fixtures = json.loads((ROOT / 'tests/fixtures/device-snapshot.json').read_text())['devices']
        self.devices = {d['metadata']['deviceType']: Device(d['metadata'], d['discovery'], d['registers']) for d in fixtures}
        self.coordinator = SimpleNamespace(data=self.devices, energy=SimpleNamespace(data={}, billing=None),
                                           last_commands={}, apply=AsyncMock())

    def test_english_is_source_and_turkish_has_matching_keys_and_placeholders(self):
        self.assertEqual(json.loads((COMPONENT / 'strings.json').read_text()), self.catalogs['en'])
        self.assertEqual(shape(self.catalogs['en']), shape(self.catalogs['tr']))

        def visit(en, tr):
            if isinstance(en, dict):
                for key in en:
                    visit(en[key], tr[key])
            elif isinstance(en, str):
                self.assertTrue(en.strip())
                self.assertTrue(tr.strip())
                self.assertEqual(set(re.findall(r'{(\w+)}', en)), set(re.findall(r'{(\w+)}', tr)))

        visit(self.catalogs['en'], self.catalogs['tr'])

    def test_native_entity_state_and_selector_keys_are_valid_slugs(self):
        valid = re.compile(r'^(?!.+[_-]{2})(?![_-])[a-z0-9-_]+(?<![_-])$')
        for catalog in self.catalogs.values():
            for platform, entities in catalog['entity'].items():
                self.assertRegex(platform, valid)
                for key, definition in entities.items():
                    self.assertRegex(key, valid)
                    for state in definition.get('state', {}):
                        self.assertRegex(state, valid)
            for selector in catalog['selector'].values():
                for option in selector['options']:
                    self.assertRegex(option, valid)

    def test_all_emitted_entities_keep_ids_and_have_translations(self):
        for platform in ('climate', 'select', 'switch', 'number', 'button', 'time', 'sensor', 'binary_sensor'):
            module = importlib.import_module(f'custom_components.vestel_appliances.{platform}')
            for uuid, state in self.devices.items():
                for entity in module._entities(self.coordinator, uuid, state):
                    with self.subTest(platform=platform, uuid=uuid, unique_id=entity._attr_unique_id):
                        description = getattr(entity, 'entity_description', None)
                        key = getattr(entity, '_attr_translation_key', None) or getattr(description, 'translation_key', None)
                        self.assertIsNotNone(key)
                        self.assertIn(key, self.catalogs['en']['entity'][platform])
                        self.assertTrue(entity._attr_unique_id.startswith(uuid + '_'))
                        if platform != 'climate':
                            self.assertFalse('_attr_name' in entity.__dict__)
                        if platform == 'select':
                            translated_states = self.catalogs['en']['entity'][platform][key]['state']
                            for option in entity.options:
                                self.assertIn(option, translated_states)
                        if platform == 'sensor' and state.find(getattr(entity, 'key', '')):
                            definition = state.find(entity.key)
                            if description.options:
                                self.assertEqual(description.device_class, 'enum')
                                self.assertEqual(set(description.options), set(self.catalogs['en']['entity'][platform][key]['state']))

    async def test_select_sends_same_vendor_value_for_canonical_token(self):
        module = importlib.import_module('custom_components.vestel_appliances.select')
        state = self.devices['RF']
        definition = state.find_suffix('.Setting.Mode', 'settings')
        entity = module.Setting(self.coordinator, 'RF', definition)
        self.assertIn('eco', entity.options)
        await entity.async_select_option('eco')
        self.coordinator.apply.assert_awaited_once_with('RF', updates=[(definition['key'], 16)])
        key = entity._attr_translation_key
        self.assertEqual(self.catalogs['en']['entity']['select'][key]['state']['eco'], 'Economy')
        self.assertEqual(self.catalogs['tr']['entity']['select'][key]['state']['eco'], 'Ekonomi')

    async def test_program_choice_and_selected_program_sensor_share_token(self):
        select = importlib.import_module('custom_components.vestel_appliances.select')
        sensor = importlib.import_module('custom_components.vestel_appliances.sensor')
        state = self.devices['WD']
        programs = [p for p in state.discovery['programs'] if not p['key'].endswith('.Reset')]
        entity = select.Program(self.coordinator, 'WD', {'key': 'program', 'programs': programs})
        status = sensor.Status(self.coordinator, 'WD', state.find_suffix('.SelectedProgram', 'status'))
        self.assertEqual(entity.current_option, status.native_value)
        self.assertIn(status.native_value, entity.options)
        target = programs[0]
        await entity.async_select_option(choice(target['key']))
        self.coordinator.apply.assert_awaited_once_with('WD', updates=[(target['key'], target['commandValue'])])

    async def test_climate_fan_mode_uses_translated_canonical_tokens(self):
        climate = importlib.import_module('custom_components.vestel_appliances.climate')
        entity = climate.Climate(self.coordinator, 'AC', {'key': 'climate'})
        self.assertIn('auto', entity.fan_modes)
        await entity.async_set_fan_mode('auto')
        self.coordinator.apply.assert_awaited_once()
        self.assertEqual(self.coordinator.apply.await_args.args, ('AC',))
        states = self.catalogs['tr']['entity']['climate']['climate']['state_attributes']['fan_mode']['state']
        self.assertEqual(states['auto'], 'Otomatik')

    def test_known_errors_have_native_translations_and_safe_english_fallbacks(self):
        for key, message in DEFAULT_MESSAGES.items():
            for catalog in self.catalogs.values():
                self.assertIn(key, catalog['exceptions'])
            placeholders = {'http_status': '503'} if '{http_status}' in message else {}
            error = user_error(SchemaError(key, placeholders=placeholders))
            self.assertEqual(error.translation_domain, DOMAIN)
            self.assertEqual(error.translation_key, key)
            self.assertEqual(error.translation_placeholders, placeholders)
            self.assertEqual(str(error), message.format(**placeholders))

    def test_direct_user_errors_are_declared_and_names_preserve_domain(self):
        for path in COMPONENT.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'user_error', 'ApiError', 'AuthError'}:
                    if node.args and isinstance(node.args[0], ast.Constant):
                        self.assertIn(node.args[0].value, DEFAULT_MESSAGES, path.name)
        manifest = json.loads((COMPONENT / 'manifest.json').read_text())
        self.assertEqual(manifest['name'], APP_NAME)
        self.assertEqual(APP_NAME, 'Vestel Smart Life')
        self.assertEqual(manifest['domain'], 'vestel_appliances')
        self.assertEqual(choice('LaundryCare.WasherDryer.Program.Cotton'), 'cotton')
        self.assertEqual(translation_key('Climate.AirConditioner.Setting.Fan.Speed'), 'climate_air_conditioner_setting_fan_speed')
