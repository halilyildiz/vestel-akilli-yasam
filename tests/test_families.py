"""Synthetic protocol contracts derived from APK facts, not private captures."""

from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import test_coordinator  # noqa: F401 -- shared minimal Home Assistant runtime
from custom_components.vestel_appliances.api import Api
from custom_components.vestel_appliances.coordinator import Coordinator
from custom_components.vestel_appliances.discovery import prepare_discovery
from custom_components.vestel_appliances.families import FAMILY_PROFILES
from custom_components.vestel_appliances.fields import SchemaError
from custom_components.vestel_appliances.protocol import Device


def enum(key, register, values):
    return {'key':key,'commandName':register,'valueType':'Enum',
            'values':[{'commandValue':value,'value':key+'.'+name} for name,value in values]}


def washing_machine(model='T2'):
    prefix='LaundryCare.WashingMachine.'
    program=prefix+'Program.Cotton'
    temperature=prefix+'Option.Temperature'
    schema={'deviceType':'WM',
        'programs':[{'key':program,'commandName':'WMFORPR','commandValue':3,'valueType':'Enum',
                     'includedOptions':[{'key':temperature,'values':[{'value':temperature+'.30Degree'}]}]}],
        'options':[enum(temperature,'WMUISET',[('30Degree',3),('60Degree',6)])],
        'commands':[{'key':prefix+'Command.'+name,'commandName':'WMDCPST',
                     'valueType':'Enum','commandValue':value} for name,value in [('Start',1),('Pause',3)]],
        'status':[enum(prefix+'Status.SelectedProgram','WMFORPR',[('Cotton',3)]),
                  enum(prefix+'Status.ExecutionState','WMDCPST',
                       [('Selection',0),('Program',1),('InDelay',2),('Pause',3),('EndMode',4)]),
                  {'key':prefix+'Status.RemoteControlOn','valueType':'Boolean',
                   'commandName':'WMDOORS','position':2,'length':1,'commandValue':1}]}
    metadata={'deviceType':'WM','deviceId':'synthetic-wm','deviceModel':model,
              'wifiCardType':'HM03','connected':True}
    return Device(metadata,prepare_discovery(schema,'WM'),
                  {'WMFORPR':'00003','WMDCPST':'00000','WMDOORS':'00004','WMUISET':'00003'})


def monitoring(family):
    prefix='LaundryCare.TumbleDryer' if family=='TD' else 'Cooking.Oven'
    register='TDDCPST' if family=='TD' else 'OVGENMO'
    suffix='CurrentProgramState' if family=='TD' else 'ExecutionState'
    schema={'deviceType':family,
        'commands':[{'key':prefix+'.Command.Start','valueType':'Enum','commandName':register,'commandValue':2}],
        'status':[enum(prefix+'.Status.'+suffix,register,[('Program',2),('Selection',1)])]}
    if family=='TD':
        schema['status'].append({'key':prefix+'.Status.RemoteControl','valueType':'Boolean',
                                 'commandName':'TDREMTC','length':1,'position':0})
    return Device({'deviceType':family,'wifiCardType':'HM03','deviceId':'synthetic-'+family},
                  prepare_discovery(schema,family),{register:'00002','TDREMTC':'00001'})


class FamilyContracts(unittest.TestCase):
    def test_coverage_has_explicit_levels(self):
        self.assertEqual(set(FAMILY_PROFILES),{'AC','WD','DW','RF','WM','FD','TD','OV'})
        self.assertEqual(FAMILY_PROFILES['WM'].support_level,'experimental_controls')
        self.assertEqual(FAMILY_PROFILES['FD'].support_level,'experimental_controls')
        self.assertFalse(FAMILY_PROFILES['TD'].writable)
        self.assertFalse(FAMILY_PROFILES['OV'].writable)

    def test_washer_program_and_command_encoding(self):
        for model in ('T2','T3','IC'):
            with self.subTest(model=model):
                state=washing_machine(model)
                program=state.discovery['programs'][0]
                self.assertEqual(state.build([(program['key'],3)]),['WMFORPR00003'])
                command=state.find_suffix('.Command.Start','commands')
                self.assertEqual(state.command(command['key']),'WMDCPST00001')
                expected=state.expected_readback(['WMDCPST00001'],command=command['key'])
                self.assertFalse(expected.matches({'WMDCPST':'00000'}))
                self.assertTrue(expected.matches({'WMDCPST':'00001'}))

    def test_washer_remote_control_is_required_for_every_write(self):
        state=washing_machine();state.registers['WMDOORS']='00000'
        for definition in state.definitions('programs','options','commands'):
            with self.subTest(key=definition['key']),self.assertRaisesRegex(SchemaError,'Enable remote control'):
                state.validate(definition)

    def test_washer_program_constraints_and_state_are_preserved(self):
        state=washing_machine();option=state.discovery['options'][0]
        self.assertEqual([v['commandValue'] for v in state.values(option)],[3])
        with self.assertRaisesRegex(SchemaError,'unsupported for the selected'):state.build([(option['key'],6)])
        state.registers['WMDCPST']='00001'
        with self.assertRaisesRegex(SchemaError,'return to program selection'):
            state.build([(state.discovery['programs'][0]['key'],3)])
        with self.assertRaisesRegex(SchemaError,'already running'):
            state.command(state.find_suffix('.Command.Start','commands')['key'])
        self.assertEqual(state.command(state.find_suffix('.Command.Pause','commands')['key']),'WMDCPST00003')

    def test_fd_uses_its_own_schema_and_preserves_neighbor_bits(self):
        key='Refrigeration.FridgeCooler.Setting.Main.Temperature'
        setting=enum(key,'FDMAINA',[('4C',2),('6C',3)])
        setting.update(position=4,length=4)
        schema=prepare_discovery({'deviceType':'FD','settings':[setting]},'FD')
        state=Device({'deviceType':'FD'},schema,{'FDMAINA':'00175'})
        self.assertEqual(state.build([(key,3)]),['FDMAINA00063'])
        expected=state.expected_readback(['FDMAINA00063'],updates=[(key,3)])
        self.assertTrue(expected.matches({'FDMAINA':'00048'}))
        self.assertFalse(expected.matches({'FDMAINA':'00032'}))
        self.assertIsNone(state.refrigerator_door_open())

    def test_monitoring_projection_removes_all_write_definitions(self):
        for family in ('TD','OV'):
            state=monitoring(family)
            self.assertEqual(state.support_level,'monitoring')
            self.assertFalse(state.writable)
            self.assertEqual(state.definitions('commands','settings','options','programs'),[])
            with self.assertRaisesRegex(SchemaError,'monitoring only'):
                state.validate({'key':'arbitrary'})

    def test_dryer_boolean_mapping_is_narrow_and_does_not_mutate_raw_schema(self):
        raw={'deviceType':'TD','status':[
            {'key':'LaundryCare.TumbleDryer.Status.RemoteControl','valueType':'Boolean',
             'commandName':'TDREMTC','position':0,'length':1},
            {'key':'LaundryCare.TumbleDryer.Status.Other','valueType':'Boolean',
             'commandName':'TDOTHER','position':0,'length':1}]}
        before=copy.deepcopy(raw);schema=prepare_discovery(raw,'TD')
        state=Device({'deviceType':'TD'},schema,{'TDREMTC':'00001','TDOTHER':'00001'})
        self.assertIs(state.decode(schema['status'][0]),True)
        self.assertIsNone(state.decode(schema['status'][1]))
        self.assertEqual(raw,before)

    def test_hca_component_schema_cannot_be_misrouted_to_legacy(self):
        with self.assertRaisesRegex(SchemaError,'device_type_mismatch'):
            prepare_discovery({'deviceType':'Washer','components':[]},'WM')

    def test_fault_definitions_remain_resolvable_for_entity_availability(self):
        state=monitoring('OV')
        definition={'key':'Cooking.Oven.Error.TemperatureSensor','valueType':'Boolean',
                    'commandName':'OVERRMO','position':0,'length':1,'commandValue':1}
        state.discovery['errors']=[definition]
        self.assertIs(state.find(definition['key']),definition)

    def test_undocumented_unsigned_temperature_encoding_is_not_a_measurement(self):
        definition={'key':'Refrigeration.FridgeFreezer.Status.FreezerSensorTemperature',
            'commandName':'FDFRZTE','valueType':'Integer',
            'valueLimits':{'min':-50,'max':50,'unit':'celcius','scale':0}}
        state=Device({'deviceType':'FD'},{'status':[definition]},{'FDFRZTE':'65518'})
        self.assertIsNone(state.decode(definition))
        state.registers['FDFRZTE']='00004'
        self.assertEqual(state.decode(definition),4)

    def test_new_numeric_sensor_units_require_explicit_unscaled_schema(self):
        from custom_components.vestel_appliances.entity_descriptions import sensor_description
        temperature={'key':'Cooking.Oven.Status.CurrentMeasuredTemperature','valueType':'Integer',
                     'valueLimits':{'unit':'celsius','scale':0}}
        duration={'key':'LaundryCare.TumbleDryer.Status.RemainingTimeDry','valueType':'Integer',
                  'valueLimits':{'unit':'minute','scale':0}}
        self.assertEqual(sensor_description(temperature).native_unit_of_measurement,'°C')
        self.assertEqual(sensor_description(duration).native_unit_of_measurement,'min')
        temperature['valueLimits']['scale']=1
        self.assertIsNone(sensor_description(temperature).native_unit_of_measurement)


class FamilyDiscovery(unittest.IsolatedAsyncioTestCase):
    async def test_new_washer_is_discovered_and_bad_family_model_is_isolated(self):
        state=washing_machine()
        metadata=state.metadata
        api=SimpleNamespace(devices=AsyncMock(return_value=[metadata]),
            discovery=AsyncMock(return_value=state.discovery),status=AsyncMock(return_value=state.registers))
        coordinator=Coordinator(None,SimpleNamespace(data={'home_id':'synthetic-home'}),api)
        result=await coordinator._async_update_data()
        self.assertTrue(result[metadata['deviceId']].read_ok)
        api.devices.return_value.append({'deviceId':'bad-oven','deviceType':'OV','wifiCardType':'HM03'})
        api.discovery.side_effect=lambda uuid:state.discovery if uuid==metadata['deviceId'] else {'deviceType':'Oven','components':[]}
        result=await coordinator._async_update_data()
        self.assertTrue(result[metadata['deviceId']].read_ok)
        self.assertFalse(result['bad-oven'].read_ok)
        self.assertIn('bad-oven',coordinator.compatibility_errors)

    async def test_monitoring_service_rejects_write_before_network_access(self):
        for family in ('TD','OV'):
            api=SimpleNamespace(devices=AsyncMock(),status=AsyncMock(),send=AsyncMock())
            coordinator=Coordinator(None,SimpleNamespace(data={'home_id':'synthetic-home'}),api)
            coordinator.data={'device':monitoring(family)}
            with self.assertRaisesRegex(Exception,'monitoring only'):
                await coordinator.apply('device',command='arbitrary')
            api.devices.assert_not_awaited();api.status.assert_not_awaited();api.send.assert_not_awaited()

    async def test_other_backends_counted_without_entering_legacy_pipeline(self):
        api=Api(None,{})
        records=[washing_machine().metadata]
        api.request=AsyncMock(return_value={'items':{'homeappliances':records,
            'thirdpartyDevices':[{'deviceId':'private-id','password':'private-secret'}],
            'televisions':[],'chargers':[{}],'pairedDevices':None}})
        self.assertIs(await api.devices('synthetic-home'),records)
        self.assertEqual(api.inventory_summary,{'homeappliances':1,'thirdpartyDevices':1,'televisions':0,'chargers':1})

    async def test_monitoring_families_create_no_control_entities_even_with_raw_commands(self):
        # Use the established HA platform stubs without duplicating their runtime.
        from test_translations import TranslationTests
        fixture=TranslationTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for family in ('TD','OV'):
            state=monitoring(family)
            state.discovery['commands']=[{'key':'synthetic.Command.Start','commandName':'OVGENMO','commandValue':2}]
            for platform in ('button','select','switch','number','time','climate'):
                module=importlib.import_module('custom_components.vestel_appliances.'+platform)
                self.assertEqual(module._entities(None,'synthetic',state),[])
