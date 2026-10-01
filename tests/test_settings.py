"""Compatibility and command checks for shared tables and named setting codes."""

from enum import IntEnum
import typing
import unittest
from unittest.mock import Mock

from pyvisa.resources import MessageBasedResource

import sr830
import sr830.settings as settings
import virtual_sr830


ENUM_TABLES = (
    (settings.ReferenceSource, 'reference_sources'),
    (settings.ReferenceTrigger, 'triggers'),
    (settings.InputConfiguration, 'input_configurations'),
    (settings.InputShieldGrounding, 'groundings'),
    (settings.InputCoupling, 'input_couplings'),
    (settings.LineNotchFilter, 'input_line_notch_filter_statuses'),
    (settings.ReserveMode, 'reserve_modes'),
    (settings.SynchronousFilter, 'synchronous_filter_statuses'),
    (settings.Channel1Display, 'display_ch1'),
    (settings.Channel2Display, 'display_ch2'),
    (settings.Channel1Ratio, 'ratio_ch1'),
    (settings.Channel2Ratio, 'ratio_ch2'),
    (settings.FrontPanelOutputSource, 'front_panel_output_sources_ch1'),
    (settings.FrontPanelOutputSource, 'front_panel_output_sources_ch2'),
    (settings.OutputInterface, 'output_interfaces'),
    (settings.SwitchState, 'key_click_states'),
    (settings.SwitchState, 'alarm_statuses'),
    (settings.EndOfBufferMode, 'end_of_buffer_modes'),
    (settings.TriggerStartMode, 'trigger_start_modes'),
    (settings.DataTransferMode, 'data_transfer_modes'),
    (settings.LocalMode, 'local_modes'),
    (settings.GpibOverrideRemote, 'gpib_override_remote_conditions'),
)

PROPERTY_CODES = (
    ('reference_source', settings.ReferenceSource.INTERNAL, 'FMOD'),
    ('reference_trigger', settings.ReferenceTrigger.TTL_FALLING_EDGE, 'RSLP'),
    ('input_configuration', settings.InputConfiguration.CURRENT_100_MOHM, 'ISRC'),
    ('input_shield_grounding', settings.InputShieldGrounding.GROUND, 'IGND'),
    ('input_coupling', settings.InputCoupling.DC, 'ICPL'),
    ('line_notch_filter_status', settings.LineNotchFilter.BOTH, 'ILIN'),
    ('reserve_mode', settings.ReserveMode.LOW_NOISE, 'RMOD'),
    ('sync_filter_status', settings.SynchronousFilter.BELOW_200_HZ, 'SYNC'),
    ('output_interface', settings.OutputInterface.GPIB, 'OUTX'),
    ('key_click_state', settings.SwitchState.ON, 'KCLK'),
    ('alarm_status', settings.SwitchState.ON, 'ALRM'),
    ('end_of_buffer_mode', settings.EndOfBufferMode.LOOP, 'SEND'),
    ('trigger_start_mode', settings.TriggerStartMode.START_SCAN, 'TSTR'),
    ('data_transfer_mode', settings.DataTransferMode.WINDOWS, 'FAST'),
    ('local_mode', settings.LocalMode.LOCAL_LOCKOUT, 'LOCL'),
    ('gpib_override_remote', settings.GpibOverrideRemote.ENABLED, 'OVRM'),
    ('power_on_status_clear_bit', settings.SwitchState.ON, '*PSC'),
)


class SettingsTests(unittest.TestCase):
    def test_all_tables_are_shared_class_variables(self):
        hints = typing.get_type_hints(settings._Settings)
        hardware = sr830.sr830()
        virtual = virtual_sr830.sr830()
        for name, hint in hints.items():
            with self.subTest(name=name):
                self.assertIs(typing.get_origin(hint), typing.ClassVar)
                self.assertIs(getattr(hardware, name), getattr(virtual, name))
                self.assertIs(getattr(hardware, name), getattr(settings._Settings, name))
                self.assertNotIn(name, vars(hardware))
                self.assertNotIn(name, vars(virtual))

    def test_numeric_tables_preserve_units_and_indices(self):
        driver = sr830.sr830()
        self.assertEqual(len(driver.sensitivities), 27)
        self.assertEqual((driver.sensitivities[0], driver.sensitivities[26]), (2e-9, 1.0))
        self.assertEqual(len(driver.time_constants), 20)
        self.assertEqual((driver.time_constants[0], driver.time_constants[19]), (10e-6, 30e3))
        self.assertEqual(driver.low_pass_filter_slopes, (6, 12, 18, 24))
        self.assertEqual(driver.expands, (0, 10, 100))
        self.assertEqual((driver.sample_rates[0], driver.sample_rates[13], driver.sample_rates[14]), (0.0625, 512, 'Trigger'))
        for cls in (sr830.sr830, virtual_sr830.sr830):
            driver = cls()
            if cls is sr830.sr830:
                driver._instr = Mock(spec=MessageBasedResource)
                driver._instr.query.side_effect = ['0', '19']
            else:
                driver.sensitivity = 0
                driver.time_constant = 19
            self.assertEqual(driver.sensitivities[driver.sensitivity], 2e-9)
            self.assertEqual(driver.time_constants[driver.time_constant], 30e3)

    def test_table_contents_cannot_be_mutated(self):
        driver = sr830.sr830()
        with self.assertRaises(TypeError):
            driver.sensitivities[0] = 1.0
        with self.assertRaises(TypeError):
            driver._enable_register_cmd_dict['error'] = 'BROKEN'
        with self.assertRaises(TypeError):
            driver._error_status_byte[1][1] = 'BROKEN'

    def test_enum_exports_and_mapping_indices(self):
        for enum, table_name in ENUM_TABLES:
            with self.subTest(enum=enum.__name__, table=table_name):
                self.assertTrue(issubclass(enum, IntEnum))
                self.assertIs(getattr(sr830, enum.__name__), enum)
                self.assertIs(getattr(virtual_sr830, enum.__name__), enum)
                table = getattr(sr830.sr830, table_name)
                self.assertEqual([int(member) for member in enum], list(range(len(table))))
        self.assertEqual(sr830.sr830.local_modes[settings.LocalMode.LOCAL_LOCKOUT], 'Local lockout')
        self.assertEqual(sr830.sr830.reference_sources[settings.ReferenceSource.INTERNAL], 'internal')
        self.assertEqual(sr830.sr830.output_interfaces[settings.OutputInterface.GPIB], 'GPIB')

    def test_enums_and_integers_emit_identical_commands(self):
        hardware = sr830.sr830()
        hardware._instr = Mock(spec=MessageBasedResource)
        virtual = virtual_sr830.sr830()
        for name, code, command in PROPERTY_CODES:
            for value in (code, int(code)):
                with self.subTest(name=name, value=value):
                    setattr(hardware, name, value)
                    hardware._instr.write.assert_called_with(f'{command} {int(code)}')
                    hardware._instr.query.return_value = str(int(code))
                    result = getattr(hardware, name)
                    self.assertIs(type(result), int)
                    self.assertEqual(result, int(code))
                    setattr(virtual, name, value)
                    result = getattr(virtual, name)
                    self.assertIs(type(result), int)
                    self.assertEqual(result, int(code))

    def test_invalid_integer_codes_still_raise(self):
        for cls in (sr830.sr830, virtual_sr830.sr830):
            driver = cls()
            for name, code, command in PROPERTY_CODES:
                invalid = max(int(member) for member in type(code)) + 1
                with self.subTest(driver=cls.__module__, name=name):
                    with self.assertRaises(ValueError):
                        setattr(driver, name, invalid)

    def test_display_enums_preserve_integer_tuple_returns(self):
        hardware = sr830.sr830()
        hardware._instr = Mock(spec=MessageBasedResource)
        virtual = virtual_sr830.sr830()
        for channel, display, ratio in (
            (1, settings.Channel1Display.AUX_IN_2, settings.Channel1Ratio.AUX_IN_1),
            (2, settings.Channel2Display.PHASE, settings.Channel2Ratio.AUX_IN_4),
        ):
            hardware.set_display(channel, display, ratio)
            hardware._instr.write.assert_called_with(f'DDEF {channel}, {int(display)}, {int(ratio)}')
            virtual.set_display(channel, display, ratio)
            result = virtual.get_display(channel)
            self.assertEqual(result, (int(display), int(ratio)))
            self.assertTrue(all(type(value) is int for value in result))
            hardware.set_front_output(channel, settings.FrontPanelOutputSource.COMPONENT)
            hardware._instr.write.assert_called_with(f'FPOP {channel}, 1')
            virtual.set_front_output(channel, settings.FrontPanelOutputSource.COMPONENT)
            self.assertIs(type(virtual.get_front_output(channel)), int)
            self.assertEqual(virtual.get_front_output(channel), 1)

    def test_connect_accepts_named_output_interface(self):
        virtual = virtual_sr830.sr830()
        virtual.connect('TCPIP0::example.invalid::1234::SOCKET', output_interface=settings.OutputInterface.GPIB)
        self.assertIs(type(virtual.output_interface), int)
        self.assertEqual(virtual.output_interface, 1)
        virtual.disconnect()


if __name__ == '__main__':
    unittest.main()
