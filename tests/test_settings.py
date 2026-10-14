"""Compatibility and command checks for named setting codes."""

from enum import IntEnum
import unittest
from unittest.mock import Mock

from pyvisa.resources import MessageBasedResource

import sr830
import sr830.settings as settings
import virtual_sr830


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
    def test_categorical_enums_are_shared_and_use_command_codes(self):
        for enum in {type(code) for name, code, command in PROPERTY_CODES}:
            with self.subTest(enum=enum.__name__):
                self.assertTrue(issubclass(enum, IntEnum))
                self.assertIs(getattr(sr830, enum.__name__), enum)
                self.assertIs(getattr(virtual_sr830, enum.__name__), enum)
                self.assertEqual([int(member) for member in enum], list(range(len(enum))))

    def test_enums_and_integers_emit_identical_commands(self):
        hardware = sr830.SR830()
        hardware._instr = Mock(spec=MessageBasedResource)
        virtual = virtual_sr830.VirtualSR830()
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
        for cls in (sr830.SR830, virtual_sr830.VirtualSR830):
            driver = cls()
            for name, code, command in PROPERTY_CODES:
                invalid = max(int(member) for member in type(code)) + 1
                with self.subTest(driver=cls.__module__, name=name):
                    with self.assertRaises(ValueError):
                        setattr(driver, name, invalid)

    def test_display_enums_preserve_integer_tuple_returns(self):
        hardware = sr830.SR830()
        hardware._instr = Mock(spec=MessageBasedResource)
        virtual = virtual_sr830.VirtualSR830()
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
        virtual = virtual_sr830.VirtualSR830()
        virtual.connect('TCPIP0::example.invalid::1234::SOCKET', output_interface=settings.OutputInterface.GPIB)
        self.assertIs(type(virtual.output_interface), int)
        self.assertEqual(virtual.output_interface, 1)
        virtual.disconnect()


if __name__ == '__main__':
    unittest.main()
