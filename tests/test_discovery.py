"""Offline model validation and device addition regression tests."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
import test_coordinator  # noqa: F401 -- shared HA runtime
from custom_components.vestel_appliances.coordinator import Coordinator
from custom_components.vestel_appliances.discovery import validate_discovery
from custom_components.vestel_appliances.fields import SchemaError
from custom_components.vestel_appliances.live import LiveUpdates

DEVICES=json.loads((Path(__file__).parent/'fixtures/device-snapshot.json').read_text())['devices']

class SchemaTests(unittest.TestCase):
    def test_real_models_preserved(self):
        for d in DEVICES:
            s=copy.deepcopy(d['discovery'])
            self.assertIs(validate_discovery(s,d['metadata']['deviceType']),s)
            self.assertEqual(s,d['discovery'])

    def test_malformed_models_fail_closed(self):
        for change in (
            lambda s:s.update(deviceType='RF'),
            lambda s:s.update(settings=None),
            lambda s:s['settings'][0].update(valueType='Unknown'),
            lambda s:s['settings'][0].update(commandName='bad'),
            lambda s:s['settings'][0].update(position=16,length=2),
            lambda s:s['settings'][0].update(includedSettings='invalid'),
            lambda s:s['settings'][0].update(valueLimits={'min':'bad'}),
            lambda s:s.update(settingRelations=[None]),
        ):
            s=copy.deepcopy(DEVICES[0]['discovery']);change(s)
            with self.assertRaises(SchemaError):validate_discovery(s,'AC')

class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.d=copy.deepcopy(DEVICES[-1])
        self.meta={**self.d['metadata'],'deviceId':'healthy'}
        self.api=SimpleNamespace(devices=AsyncMock(return_value=[self.meta]),
            discovery=AsyncMock(return_value=self.d['discovery']),status=AsyncMock(return_value=self.d['registers']))
        self.c=Coordinator(None,SimpleNamespace(data={'home_id':'home'}),self.api)

    async def test_new_model_arrives_during_runtime(self):
        self.assertEqual(set(await self.c._async_update_data()),{'healthy'})
        self.api.devices.return_value.append({**self.meta,'deviceId':'new','variant':'different'})
        result=await self.c._async_update_data()
        self.assertEqual(set(result),{'healthy','new'})
        self.assertTrue(result['new'].read_ok)

    async def test_unsupported_only_account_remains_loaded_and_recovers(self):
        self.api.devices.return_value=[{'deviceType':'OV','deviceId':'oven'}]
        self.assertEqual(await self.c._async_update_data(),{})
        self.assertEqual(self.c.unsupported_types,{'OV':1})
        self.api.discovery.assert_not_called()
        self.api.devices.return_value=[self.meta]
        self.assertIn('healthy',await self.c._async_update_data())
        self.assertEqual(self.c.unsupported_types,{})

    async def test_bad_model_isolated_and_recovers(self):
        self.api.devices.return_value.append({**self.meta,'deviceId':'bad'})
        async def schema(uuid):return {} if uuid=='bad' else self.d['discovery']
        self.api.discovery.side_effect=schema
        result=await self.c._async_update_data()
        self.assertTrue(result['healthy'].read_ok)
        self.assertFalse(result['bad'].read_ok)
        self.assertIn('bad',self.c.compatibility_errors)
        self.api.discovery.side_effect=None
        result=await self.c._async_update_data()
        self.assertTrue(result['bad'].read_ok)
        self.assertEqual(self.c.compatibility_errors,{})

    async def test_firmware_refreshes_schema(self):
        await self.c._async_update_data();await self.c._async_update_data()
        self.assertEqual(self.api.discovery.await_count,1)
        self.meta['wifiVersion']='future'
        await self.c._async_update_data()
        self.assertEqual(self.api.discovery.await_count,2)

    def test_mqtt_topology_change_requests_resubscription(self):
        c=SimpleNamespace(data={'one':SimpleNamespace(metadata={})})
        live=LiveUpdates(None,None,c)
        live._check_devices();live._topology_changed.clear()
        c.data['two']=SimpleNamespace(metadata={})
        live._check_devices();self.assertTrue(live._topology_changed.is_set())
        live._topology_changed.clear();live._check_devices()
        self.assertFalse(live._topology_changed.is_set())

class DynamicTests(unittest.TestCase):
    def test_add_device_add_field_no_duplicates_and_cleanup(self):
        import test_entity_descriptions  # noqa: F401 -- sensor stubs
        from custom_components.vestel_appliances.dynamic import setup_dynamic_entities
        c=SimpleNamespace(data={'one':SimpleNamespace(discovery={'keys':['a']})},
            async_add_listener=Mock(return_value='unsubscribe'),platform_errors=set(),set_platform_error=Mock())
        hass=SimpleNamespace(data={'vestel_appliances':{'entry':c}})
        entry=SimpleNamespace(entry_id='entry',async_on_unload=Mock())
        add=Mock()
        def factory(c,uuid,state):return [SimpleNamespace(_attr_unique_id=uuid+k) for k in state.discovery['keys']]
        setup_dynamic_entities(hass,entry,add,factory)
        update=c.async_add_listener.call_args.args[0]
        update();self.assertEqual(add.call_count,1)
        c.data['two']=SimpleNamespace(discovery={'keys':['a']})
        update();self.assertEqual(add.call_args.args[0][0]._attr_unique_id,'twoa')
        c.data['one'].discovery={'keys':['a','b']}
        update();self.assertEqual([e._attr_unique_id for e in add.call_args.args[0]],['oneb'])
        entry.async_on_unload.assert_called_once_with('unsubscribe')

    def test_factory_failure_isolated_from_other_device(self):
        import test_entity_descriptions  # noqa: F401
        from custom_components.vestel_appliances.dynamic import setup_dynamic_entities
        c=SimpleNamespace(data={'bad':SimpleNamespace(discovery={'x':1}),
                                'good':SimpleNamespace(discovery={'x':2})},
            async_add_listener=Mock(return_value='unsubscribe'),set_platform_error=Mock())
        hass=SimpleNamespace(data={'vestel_appliances':{'entry':c}})
        entry=SimpleNamespace(entry_id='entry',async_on_unload=Mock())
        add=Mock()
        def factory(c,uuid,state):
            if uuid=='bad':raise ValueError('unsupported')
            return [SimpleNamespace(_attr_unique_id=uuid)]
        setup_dynamic_entities(hass,entry,add,factory)
        self.assertEqual([e._attr_unique_id for e in add.call_args.args[0]],['good'])
        c.set_platform_error.assert_any_call('bad',factory.__module__,True)

    def test_refreshed_description_updates_existing_entity(self):
        import test_entity_descriptions  # noqa: F401
        from custom_components.vestel_appliances.dynamic import setup_dynamic_entities
        c=SimpleNamespace(data={'one':SimpleNamespace(discovery={'position':0})},
            async_add_listener=Mock(return_value='unsubscribe'),set_platform_error=Mock())
        hass=SimpleNamespace(data={'vestel_appliances':{'entry':c}})
        entry=SimpleNamespace(entry_id='entry',async_on_unload=Mock());add=Mock()
        def factory(c,uuid,state):return [SimpleNamespace(_attr_unique_id=uuid,definition=state.discovery)]
        setup_dynamic_entities(hass,entry,add,factory)
        entity=add.call_args.args[0][0]
        c.data['one'].discovery={'position':4}
        c.async_add_listener.call_args.args[0]()
        self.assertEqual(add.call_count,1)
        self.assertEqual(entity.definition,{'position':4})

class PlatformRegressionTests(unittest.TestCase):
    def test_all_eight_platforms_preserve_existing_four_device_entity_counts(self):
        import importlib
        import sys
        import types
        from enum import IntFlag,StrEnum
        import test_entity_descriptions as stubs
        class Features(IntFlag):
            TARGET_TEMPERATURE=1;FAN_MODE=2;TURN_ON=4;TURN_OFF=8
        class Modes(StrEnum):
            AUTO='auto';COOL='cool';HEAT='heat';DRY='dry';FAN_ONLY='fan_only';OFF='off'
        modules={}
        for name,entity in [('climate','ClimateEntity'),('select','SelectEntity'),('switch','SwitchEntity'),('number','NumberEntity'),('time','TimeEntity'),('button','ButtonEntity')]:
            m=types.ModuleType('homeassistant.components.'+name)
            setattr(m,entity,type(entity,(stubs.Entity,),{}));modules[m.__name__]=m
        modules['homeassistant.components.climate'].ClimateEntityFeature=Features
        modules['homeassistant.components.climate'].HVACMode=Modes
        modules['homeassistant.components.number'].NumberMode=SimpleNamespace(BOX='box')
        sys.modules['homeassistant.const'].ATTR_TEMPERATURE='temperature'
        from custom_components.vestel_appliances.protocol import Device
        from unittest.mock import patch
        data={d['metadata']['deviceType']:Device(d['metadata'],d['discovery'],d['registers']) for d in DEVICES}
        c=SimpleNamespace(data=data,energy=SimpleNamespace(data={},billing=None))
        counts={k:0 for k in data}
        with patch.dict(sys.modules,modules):
            for platform in ('climate','select','switch','number','button','time','sensor','binary_sensor'):
                module=importlib.import_module('custom_components.vestel_appliances.'+platform)
                for uuid,state in data.items():counts[uuid]+=len(module._entities(c,uuid,state))
        self.assertEqual(counts,{'AC':49,'WD':33,'DW':36,'RF':35})

    def test_removed_device_fault_attributes_do_not_crash(self):
        import test_entity_descriptions  # noqa: F401
        from custom_components.vestel_appliances.binary_sensor import Problem
        from custom_components.vestel_appliances.protocol import Device
        d=DEVICES[-1]
        c=SimpleNamespace(data={"device":Device(d['metadata'],d['discovery'],d['registers'])},last_commands={})
        entity=Problem(c,"device")
        c.data={}
        self.assertFalse(entity.available)
        self.assertEqual(entity.extra_state_attributes['error_registers'],{})
