"""Named codes, selectors, and register bits without real hardware."""

from enum import IntEnum, IntFlag
import inspect
import typing
import unittest
from unittest.mock import Mock, patch

from pyvisa.resources import MessageBasedResource

import sr830
import sr830.settings as settings
import virtual_sr830
from test_settings import PROPERTY_CODES


NUMERIC_PROPERTIES = (
    ('sensitivity', settings.Sensitivity, 'SENS', 'sensitivities'),
    ('time_constant', settings.TimeConstant, 'OFLT', 'time_constants'),
    ('lowpass_filter_slope', settings.LowPassFilterSlope, 'OFSL', 'low_pass_filter_slopes'),
    ('sample_rate', settings.SampleRate, 'SRAT', 'sample_rates'),
)
REGISTER_TYPES = (
    (settings.StatusRegister.STANDARD_EVENT, settings.StandardEventBit, settings.StandardEventFlag, '*ESE', '*ESR?'),
    (settings.StatusRegister.SERIAL_POLL, settings.SerialPollBit, settings.SerialPollFlag, '*SRE', '*STB?'),
    (settings.StatusRegister.ERROR, settings.ErrorBit, settings.ErrorFlag, 'ERRE', 'ERRS?'),
    (settings.StatusRegister.LIA_STATUS, settings.LiaStatusBit, settings.LiaStatusFlag, 'LIAE', 'LIAS?'),
)


class EnumTests(unittest.TestCase):
    def setUp(self):
        self.hardware = sr830.sr830()
        self.resource = Mock(spec=MessageBasedResource)
        self.hardware._instr = self.resource
        self.virtual = virtual_sr830.sr830()

    def test_all_enums_are_exported_by_both_packages(self):
        for name, enum in vars(settings).items():
            if inspect.isclass(enum) and issubclass(enum, (IntEnum, IntFlag, settings.StatusRegister)) and enum.__module__ == settings.__name__:
                with self.subTest(name=name):
                    self.assertIs(getattr(sr830, name), enum)
                    self.assertIs(getattr(virtual_sr830, name), enum)

    def test_numeric_names_codes_and_physical_tables(self):
        self.assertEqual(settings.Sensitivity.x1u, 8)
        self.assertEqual(settings.Sensitivity.x200m, 24)
        self.assertEqual(settings.Sensitivity.x1, 26)
        self.assertIs(settings.Sensitivity(26), settings.Sensitivity.x1)
        self.assertIs(settings.Sensitivity.__members__['x1'], settings.Sensitivity.x1)
        for name, enum, command, table in NUMERIC_PROPERTIES:
            self.assertEqual([int(member) for member in enum], list(range(len(getattr(self.hardware, table)))))
        for member in settings.Sensitivity:
            self.assertTrue(member.name.startswith('x'))
            prefix = member.name[-1] if member.name[-1].isalpha() else ''
            number = member.name[1:-1] if prefix else member.name[1:]
            multiplier = {'n': 1e-9, 'u': 1e-6, 'm': 1e-3, '': 1}[prefix]
            self.assertAlmostEqual(self.hardware.sensitivities[member] / (int(number) * multiplier), 1)
        for member in settings.TimeConstant:
            unit, number = member.name.split('_')
            multiplier = {'us': 1e-6, 'ms': 1e-3, 's': 1, 'ks': 1e3}[unit]
            self.assertAlmostEqual(self.hardware.time_constants[member], int(number) * multiplier)
        for member in settings.LowPassFilterSlope:
            self.assertEqual(self.hardware.low_pass_filter_slopes[member], int(member.name.split('_')[1]))
        for member in settings.SampleRate:
            if member is settings.SampleRate.TRIGGER:
                self.assertEqual(self.hardware.sample_rates[member], 'Trigger')
            else:
                unit, number = member.name.split('_', 1)
                multiplier = 1e-3 if unit == 'mHz' else 1
                self.assertEqual(self.hardware.sample_rates[member], float(number.replace('_', '.')) * multiplier)

    def test_every_property_enum_member_matches_integer_behavior(self):
        properties = [(name, type(code), command) for name, code, command in PROPERTY_CODES]
        properties += [(name, enum, command) for name, enum, command, table in NUMERIC_PROPERTIES]
        for name, enum, command in properties:
            for member in enum:
                for value in (member, int(member)):
                    with self.subTest(name=name, member=member, value_type=type(value)):
                        setattr(self.hardware, name, value)
                        self.resource.write.assert_called_with(f'{command} {int(member)}')
                        self.resource.query.return_value = str(int(member))
                        self.assertIs(type(getattr(self.hardware, name)), int)
                        self.assertEqual(getattr(self.hardware, name), int(member))
                        setattr(self.virtual, name, value)
                        self.assertIs(type(getattr(self.virtual, name)), int)
                        self.assertEqual(getattr(self.virtual, name), int(member))

    def test_numeric_invalid_codes_and_wrong_enum_classes(self):
        for driver in (self.hardware, self.virtual):
            for name, enum, command, table in NUMERIC_PROPERTIES:
                for value in (-1, len(enum), settings.ReferenceSource.INTERNAL):
                    with self.subTest(name=name, value=value, driver=type(driver)):
                        with self.assertRaises(ValueError):
                            setattr(driver, name, value)
            with self.assertRaisesRegex(ValueError, 'ReferenceSource'):
                driver.reference_source = settings.LocalMode.REMOTE
        self.resource.write.assert_not_called()

    def test_display_enums_are_checked_against_channel(self):
        for driver in (self.hardware, self.virtual):
            for channel, displays, ratios in (
                (settings.Channel.CH1, settings.Channel1Display, settings.Channel1Ratio),
                (settings.Channel.CH2, settings.Channel2Display, settings.Channel2Ratio),
            ):
                for display in displays:
                    for ratio in ratios:
                        with self.subTest(channel=channel, display=display, ratio=ratio):
                            driver.set_display(channel, display, ratio)
                            if driver is self.hardware:
                                self.resource.write.assert_called_with(f'DDEF {int(channel)}, {int(display)}, {int(ratio)}')
                                self.resource.query.return_value = f'{int(display)},{int(ratio)}'
                            self.assertEqual(driver.get_display(channel), (int(display), int(ratio)))
            with self.assertRaises(ValueError):
                driver.set_display(settings.Channel.CH1, settings.Channel2Display.PHASE)
            with self.assertRaises(ValueError):
                driver.set_display(settings.Channel.CH2, settings.Channel2Display.Y, settings.Channel1Ratio.AUX_IN_1)

    def test_output_expansion_and_parameter_codes(self):
        for parameter in settings.OutputParameter:
            for expand in settings.OutputExpansion:
                for driver in (self.hardware, self.virtual):
                    driver.set_output_offset_expand(parameter, 12.5, expand)
                    if driver is self.hardware:
                        self.resource.write.assert_called_with(f'OEXP {int(parameter)}, 12.5, {int(expand)}')
                        self.resource.query.return_value = f'12.5,{int(expand)}'
                    self.assertEqual(driver.get_output_offset_expand(parameter), (12.5, int(expand)))
                    self.assertIs(type(driver.get_output_offset_expand(parameter)[1]), int)
                    driver.auto_offset(parameter)
                self.resource.write.assert_called_with(f'AOFF {int(parameter)}')
        self.assertEqual([int(x) for x in settings.OutputExpansion], [0, 1, 2])
        for driver in (self.hardware, self.virtual):
            for operation in (driver.get_output_offset_expand, driver.auto_offset):
                with self.assertRaises(ValueError):
                    operation(0)

    def test_buffer_readers_accept_channel_enums_and_reject_zero(self):
        for driver in (self.hardware, self.virtual):
            for method in (driver.get_ascii_buffer_data, driver.get_binary_buffer_data, driver.get_non_norm_buffer_data):
                with self.subTest(method=method):
                    with self.assertRaises(ValueError):
                        method(0, 0, 1)
        self.resource.query.return_value = '0'  # SEND? one-shot
        self.resource.query_ascii_values.return_value = ['1.5', '']
        for channel in settings.Channel:
            self.assertEqual(self.hardware.get_ascii_buffer_data(channel, 0, 1), (1.5,))
            self.assertEqual(self.resource.query_ascii_values.call_args.args, (f'TRCA? {int(channel)},0,1',))

    def test_measurement_selectors_and_integer_serialization(self):
        self.resource.query.return_value = '1.25'
        for parameter in settings.MeasurementParameter:
            for driver in (self.hardware, self.virtual):
                if int(parameter) <= 4:
                    driver.measure(parameter)
                else:
                    with self.assertRaises(ValueError):
                        driver.measure(parameter)
        # Mimic Python 3.10 enum string conversion to catch SNAP formatting errors.
        with patch.object(settings.MeasurementParameter, '__str__', lambda self: f'MeasurementParameter.{self.name}'):
            for second in list(settings.MeasurementParameter)[1:]:
                self.resource.query.return_value = '1.0,2.0'
                self.assertEqual(tuple(self.hardware.measure_multiple([settings.MeasurementParameter.X, second])), (1.0, 2.0))
                self.resource.query.assert_called_with(f'SNAP? 1,{int(second)}')
        for driver in (self.hardware, self.virtual):
            with self.assertRaises(ValueError):
                driver.measure(settings.OutputParameter.X)
            with self.assertRaises(ValueError):
                driver.measure_multiple([settings.MeasurementParameter.X, settings.Channel.CH2])

    def test_channel_and_auxiliary_selectors(self):
        self.resource.query.return_value = '1'
        for channel in settings.Channel:
            for driver in (self.hardware, self.virtual):
                driver.read_display(channel)
                driver.set_front_output(channel, settings.FrontPanelOutputSource.COMPONENT)
                driver.get_front_output(channel)
            self.resource.write.assert_called_with(f'FPOP {int(channel)}, 1')
        for channel in settings.AuxiliaryChannel:
            for driver in (self.hardware, self.virtual):
                driver.set_aux_out(channel, 0.5)
                driver.get_aux_out(channel)
                driver.get_aux_in(channel)
            self.resource.write.assert_called_with(f'AUXV {int(channel)}, 0.5')
        for driver in (self.hardware, self.virtual):
            with self.assertRaises(ValueError):
                driver.read_display(settings.AuxiliaryChannel.AUX1)

    def test_register_names_positions_and_masks(self):
        for register, bits, flags, enable_command, status_query in REGISTER_TYPES:
            for bit in bits:
                mask = flags[bit.name]
                self.assertEqual(int(mask), 1 << int(bit))
                for driver in (self.hardware, self.virtual):
                    driver.set_enable_register(register, mask)
                    driver.set_enable_register(register, settings.SwitchState.ON, decimal=False, bit=bit)
                self.resource.write.assert_called_with(f'{enable_command} {int(bit)},1')
                self.resource.query.return_value = '1'
                self.assertEqual(self.hardware.get_enable_register(register, bit), 1)
                self.resource.query.assert_called_with(f'{enable_command}? {int(bit)}')
                self.assertEqual(self.hardware.get_status_byte(register, bit), 1)
                self.resource.query.assert_called_with(f'{status_query} {int(bit)}')
                self.assertIsNone(self.virtual.get_enable_register(register, bit))
                self.assertIsNone(self.virtual.get_status_byte(register, bit))
            members = list(flags)
            combined = members[0] | members[-1]
            self.hardware.set_enable_register(register, combined)
            self.resource.write.assert_called_with(f'{enable_command} {int(combined)}')
            self.resource.query.return_value = str(int(combined))
            self.assertEqual(flags(self.hardware.get_status_byte(register)), combined)

    def test_register_masks_positions_and_registers_cannot_be_mixed(self):
        for driver in (self.hardware, self.virtual):
            for operation in (
                lambda: driver.get_status_byte(settings.StatusRegister.ERROR, settings.SerialPollBit.ERROR),
                lambda: driver.get_enable_register(settings.StatusRegister.ERROR, settings.ErrorFlag.RAM_ERROR),
                lambda: driver.set_enable_register(settings.StatusRegister.ERROR, settings.ErrorBit.RAM_ERROR),
                lambda: driver.set_enable_register(settings.StatusRegister.ERROR, settings.SerialPollFlag.ERROR),
                lambda: driver.set_enable_register(settings.StatusRegister.ERROR, settings.ErrorFlag.RAM_ERROR, decimal=False, bit=settings.ErrorBit.RAM_ERROR),
            ):
                with self.assertRaises(ValueError):
                    operation()
        self.resource.write.assert_not_called()
        self.resource.query.assert_not_called()

    def test_annotations_expose_enum_inputs_and_integer_getters(self):
        for cls in (sr830.sr830, virtual_sr830.sr830):
            for name, enum, command, table in NUMERIC_PROPERTIES:
                setter_hints = typing.get_type_hints(getattr(cls, name).fset)
                parameter = next(value for key, value in setter_hints.items() if key != 'return')
                self.assertEqual(set(typing.get_args(parameter)), {enum, int})
                self.assertIs(typing.get_type_hints(getattr(cls, name).fget)['return'], int)
            self.assertEqual(inspect.signature(cls.connect), inspect.signature(sr830.sr830.connect))


if __name__ == '__main__':
    unittest.main()
