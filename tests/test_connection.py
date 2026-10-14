"""Hardware-free connection lifecycle tests. Run with unittest discovery."""

import inspect
import struct
import warnings
import typing
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

import pyvisa
from pyvisa.constants import InterfaceType, SerialTermination
from pyvisa.resources import SerialInstrument

from sr830 import SR830
from virtual_sr830 import VirtualSR830


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.driver = SR830()
        self.resource = Mock(spec=SerialInstrument)
        self.manager = Mock(spec=pyvisa.ResourceManager)
        self.manager.resource_info.return_value = SimpleNamespace(
            interface_type=InterfaceType.asrl
        )
        self.manager.open_resource.return_value = self.resource

    def connect(self, **kwargs):
        self.driver.connect('alias', resource_manager=self.manager, **kwargs)

    def test_serial_inference_and_initialization(self):
        self.resource.write.side_effect = lambda command: self.assertIsNone(self.driver._instr)
        self.connect(baud_rate=19200, open_timeout=1000)
        self.manager.open_resource.assert_called_once_with('alias', open_timeout=1000)
        self.assertIs(self.driver._instr, self.resource)
        self.assertEqual(self.resource.read_termination, '\r')
        self.assertEqual(self.resource.write_termination, '\n')
        self.assertEqual(self.resource.baud_rate, 19200)
        self.assertEqual(
            [c.args[0] for c in self.resource.write.call_args_list],
            ['OUTX 0', '*ESE 255', '*SRE 255', 'ERRE 255', 'LIAE 255'],
        )

    def test_gpib_inference(self):
        self.manager.resource_info.return_value.interface_type = InterfaceType.gpib
        self.connect()
        self.assertEqual(self.resource.read_termination, '\n')
        self.resource.write.assert_any_call('OUTX 1')

    def test_ambiguous_adapters_require_explicit_interface(self):
        self.manager.resource_info.return_value.interface_type = InterfaceType.tcpip
        with self.assertRaisesRegex(ValueError, 'Cannot infer'):
            self.connect()
        self.manager.open_resource.assert_not_called()
        for interface in (0, 1):
            self.connect(output_interface=interface)
            self.assertEqual(self.resource.read_termination, '\r' if interface == 0 else '\n')
            self.driver.disconnect()

    def test_explicit_interface_overrides_transport(self):
        self.connect(output_interface=1)
        self.resource.write.assert_any_call('OUTX 1')
        self.assertEqual(self.resource.read_termination, '\n')

    def test_conflicts_are_rejected_before_opening(self):
        for kwargs in (
            {'read_termination': '\n'}, {'write_termination': 'x'},
            {'write_termination': None}, {'output_interface': 2},
            {'output_interface': 1, 'write_termination': None, 'send_end': False},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                self.connect(**kwargs)
        self.manager.open_resource.assert_not_called()

    def test_valid_terminations_are_preserved(self):
        for interface, terminator in ((0, '\r'), (0, '\r\n'), (1, '\r\n'), (1, None)):
            self.manager.resource_info.return_value.interface_type = (
                InterfaceType.asrl if interface == 0 else InterfaceType.gpib
            )
            self.connect(output_interface=interface, write_termination=terminator)
            self.assertEqual(self.resource.write_termination, terminator)
            self.driver.disconnect()

    def test_each_initialization_command_failure_closes_resource(self):
        for failed_command in range(5):
            self.resource.reset_mock()
            self.resource.write.side_effect = [None] * failed_command + [OSError('write failed')]
            with self.assertRaisesRegex(OSError, 'write failed'):
                self.connect()
            self.resource.close.assert_called_once()
            self.assertIsNone(self.driver._instr)
            self.manager.close.assert_not_called()
        self.resource.write.side_effect = None
        self.connect()  # Retry after failure.

    def test_configuration_failure_closes_resource(self):
        with patch.object(type(self.resource), 'read_termination', new_callable=PropertyMock, create=True) as attr:
            attr.side_effect = [None, OSError('configuration failed')]
            with self.assertRaisesRegex(OSError, 'configuration failed'):
                self.connect()
        self.resource.close.assert_called_once()
        self.assertIsNone(self.driver._instr)

    def test_unknown_attribute_closes_resource(self):
        with self.assertRaisesRegex(ValueError, 'not a valid'):
            self.connect(unknown_attribute=1)
        self.resource.close.assert_called_once()
        self.assertIsNone(self.driver._instr)

    def test_open_failure_leaves_instance_disconnected(self):
        self.manager.open_resource.side_effect = OSError('open failed')
        with self.assertRaisesRegex(OSError, 'open failed'):
            self.connect()
        self.assertIsNone(self.driver._instr)
        self.manager.close.assert_not_called()

    def test_close_error_does_not_mask_initialization_failure(self):
        self.resource.write.side_effect = OSError('initialization failed')
        self.resource.close.side_effect = OSError('close failed')
        with self.assertRaisesRegex(OSError, 'initialization failed'):
            self.connect()
        self.assertIsNone(self.driver._instr)

    def test_reconnect_requires_disconnect(self):
        self.connect()
        with self.assertRaisesRegex(RuntimeError, 'already connected'):
            self.connect()
        self.assertEqual(self.manager.open_resource.call_count, 1)
        self.driver.disconnect()
        self.driver.disconnect()
        self.resource.close.assert_called_once()
        self.assertIsNone(self.driver._instr)
        self.manager.close.assert_not_called()
        self.connect()

    def test_disconnect_closes_even_if_local_command_fails(self):
        self.connect()
        self.resource.write.side_effect = OSError('local failed')
        with self.assertRaisesRegex(OSError, 'local failed'):
            self.driver.disconnect()
        self.resource.close.assert_called_once()
        self.assertIsNone(self.driver._instr)
        self.driver.disconnect()

    def test_disconnect_clears_state_if_close_fails(self):
        self.connect()
        self.resource.close.side_effect = OSError('close failed')
        with self.assertRaisesRegex(OSError, 'close failed'):
            self.driver.disconnect()
        self.assertIsNone(self.driver._instr)
        self.driver.disconnect()

    def test_disconnect_tolerates_an_externally_closed_resource(self):
        self.connect()
        self.resource.write.side_effect = pyvisa.errors.InvalidSession()
        self.driver.disconnect()
        self.resource.close.assert_called_once()
        self.assertIsNone(self.driver._instr)

    def test_non_message_resource_is_closed(self):
        resource = Mock()
        self.manager.open_resource.return_value = resource
        with self.assertRaisesRegex(TypeError, 'message-based'):
            self.connect()
        resource.close.assert_called_once()
        self.assertIsNone(self.driver._instr)

    def test_default_manager_is_used_but_not_closed(self):
        with patch('sr830.sr830.pyvisa.ResourceManager', return_value=self.manager):
            self.driver.connect('ASRL1::INSTR')
        self.manager.open_resource.assert_called_once_with('ASRL1::INSTR')
        self.driver.disconnect()
        self.manager.close.assert_not_called()

    def test_context_manager_and_disconnected_io(self):
        with self.driver:
            self.connect()
        self.resource.close.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, 'not connected'):
            self.driver.reference_frequency

    def test_io_helpers_reject_disconnected_instances(self):
        operations = (
            lambda: self.driver._write('*RST'),
            lambda: self.driver._query('*IDN?'),
            lambda: self.driver._query_ascii_values('TRCA? 1,0,1'),
            lambda: self.driver._read_buffer_bytes('TRCB? 1,0,1', 4),
            lambda: setattr(self.driver, 'output_interface', 1),
        )
        for connected_then_closed in (False, True):
            if connected_then_closed:
                self.connect()
                self.driver.disconnect()
            for operation in operations:
                with self.subTest(operation=operation, previously_connected=connected_then_closed):
                    with self.assertRaisesRegex(RuntimeError, '^Instrument is not connected\\.$'):
                        operation()

    def test_io_helpers_delegate_and_preserve_responses(self):
        self.connect()
        self.resource.write.reset_mock()
        self.resource.write.return_value = 6  # PyVISA returns a byte count.
        self.assertIsNone(self.driver._write('*RST'))
        self.resource.write.assert_called_once_with('*RST')
        self.resource.query.return_value = 'SR830,1234'
        self.assertEqual(self.driver._query('*IDN?'), 'SR830,1234')
        self.resource.query.assert_called_once_with('*IDN?')
        self.resource.query_ascii_values.return_value = ['1.25', '-2.5', '']
        self.assertEqual(self.driver._query_ascii_values('TRCA? 1,0,2'), ['1.25', '-2.5', ''])
        args, kwargs = self.resource.query_ascii_values.call_args
        self.assertEqual(args, ('TRCA? 1,0,2',))
        self.assertIs(kwargs['container'], list)
        self.assertEqual(kwargs['converter'](''), '')
        self.assertEqual(kwargs['converter']('1.25'), '1.25')

    def test_io_helpers_preserve_visa_errors(self):
        self.connect()
        failure = pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_timeout)
        operations = (
            (self.resource.write, lambda: self.driver._write('*RST')),
            (self.resource.query, lambda: self.driver._query('*IDN?')),
            (self.resource.query_ascii_values, lambda: self.driver._query_ascii_values('TRCA? 1,0,1')),
        )
        for method, operation in operations:
            with self.subTest(method=method):
                method.side_effect = failure
                with self.assertRaises(pyvisa.errors.VisaIOError) as caught:
                    operation()
                self.assertIs(caught.exception, failure)
                method.side_effect = None

    def test_ascii_buffer_uses_guarded_query_and_preserves_parsing(self):
        self.connect()
        self.resource.query.return_value = '0'  # SEND? one-shot mode
        self.resource.query_ascii_values.return_value = ['1.25', '-2.5', '']
        self.assertEqual(self.driver.get_ascii_buffer_data(1, 0, 2), (1.25, -2.5))
        self.assertEqual(self.resource.query_ascii_values.call_args.args, ('TRCA? 1,0,2',))

    def test_virtual_connection_matches_api_and_preserves_settings(self):
        for name, interface in (('ASRL1::INSTR', 0), ('GPIB0::14::INSTR', 1)):
            virtual = VirtualSR830()
            virtual.reference_frequency = 1234.0
            virtual.connect(name)
            self.assertEqual(virtual.output_interface, interface)
            self.assertEqual(virtual.reference_frequency, 1234.0)
            with self.assertRaises(RuntimeError):
                virtual.connect(name)
            virtual.disconnect()
            virtual.disconnect()
            self.assertEqual(virtual.local_mode, 0)
        virtual = VirtualSR830()
        with self.assertRaises(ValueError):
            virtual.connect('TCPIP0::example.invalid::1234::SOCKET')
        virtual.connect('TCPIP0::example.invalid::1234::SOCKET', output_interface=1)
        virtual.disconnect()
        with self.assertRaises(ValueError):
            virtual.connect('ASRL1::INSTR', read_termination='\n')

    def test_tcpip_adapters_require_command_terminator(self):
        self.manager.resource_info.return_value.interface_type = InterfaceType.tcpip
        with self.assertRaises(ValueError):
            self.connect(output_interface=1, write_termination=None)
        self.manager.open_resource.assert_not_called()

    def test_local_mode_is_an_explicit_caller_setting(self):
        self.connect()
        self.assertFalse(
            any(c.args[0].startswith('LOCL') for c in self.resource.write.call_args_list)
        )
        self.driver.local_mode = 2
        self.resource.write.assert_called_with('LOCL 2')
        self.driver.local_mode = 1
        self.resource.write.assert_called_with('LOCL 1')
        for mode in (0, 1, 2):
            with self.subTest(mode=mode):
                virtual = VirtualSR830()
                virtual.local_mode = mode
                virtual.connect('ASRL1::INSTR')
                self.assertEqual(virtual.local_mode, mode)

    def test_getters_query_responses(self):
        self.connect()
        self.resource.query.side_effect = ['2,1', '1']
        self.assertEqual(self.driver.get_display(1), (2, 1))
        self.assertEqual(self.driver.gpib_override_remote, 1)
        self.assertEqual(
            [c.args[0] for c in self.resource.query.call_args_list],
            ['DDEF? 1', 'OVRM?'],
        )

    def test_set_enable_register_requires_bit_for_binary_values(self):
        self.connect()
        with self.assertRaises(ValueError):
            self.driver.set_enable_register('error', 1, decimal=False)
        self.driver.set_enable_register('error', 1, decimal=False, bit=3)
        self.resource.write.assert_any_call('ERRE 3,1')

    def test_binary_buffers_ignore_text_terminators_and_restore_framing(self):
        self.connect()
        original_end = self.resource.end_input
        # These float bytes include both text terminators.
        raw = bytes([13, 10, 128, 63])
        def read(size, **kwargs):
            self.assertEqual(size, 4)
            self.assertEqual(kwargs, {'break_on_termchar': False})
            self.assertIsNone(self.resource.read_termination)
            self.assertEqual(self.resource.end_input, SerialTermination.none)
            return raw
        self.resource.read_bytes.side_effect = read
        self.resource.query.side_effect = ['0', '0']  # OUTX?, SEND?
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.assertEqual(self.driver.get_binary_buffer_data(1, 0, 1), struct.unpack('<f', raw))
        self.resource.write.assert_any_call('TRCB? 1,0,1')
        self.assertEqual(self.resource.read_termination, '\r')
        self.assertEqual(self.resource.end_input, original_end)
        self.resource.read_bytes.side_effect = None
        self.resource.read_bytes.return_value = struct.pack('<hh', 10, 124)
        self.resource.query.side_effect = ['0', '0']
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.assertEqual(self.driver.get_non_norm_buffer_data(1, 0, 1), (10.0,))
        self.resource.write.assert_any_call('TRCL? 1,0,1')

    def test_binary_read_failure_restores_text_framing(self):
        self.connect()
        original_end = self.resource.end_input
        self.resource.query.side_effect = ['1', '0']
        self.resource.read_bytes.side_effect = OSError('read failed')
        with self.assertRaisesRegex(OSError, 'read failed'):
            self.driver.get_binary_buffer_data(1, 0, 1)
        self.assertEqual(self.resource.read_termination, '\r')
        self.assertEqual(self.resource.end_input, original_end)

    def test_all_driver_methods_have_resolvable_annotations(self):
        for cls in (SR830, VirtualSR830):
            self.assertEqual(inspect.signature(cls.connect), inspect.signature(SR830.connect))
            for name, member in vars(cls).items():
                functions = [member] if inspect.isfunction(member) else []
                if isinstance(member, property):
                    functions = [f for f in (member.fget, member.fset) if f is not None]
                for function in functions:
                    hints = typing.get_type_hints(function)
                    self.assertIn('return', hints, name)
                    for parameter in inspect.signature(function).parameters:
                        if parameter != 'self':
                            self.assertIn(parameter, hints, name)


if __name__ == '__main__':
    unittest.main()
