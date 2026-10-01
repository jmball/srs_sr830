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

from sr830 import sr830
from virtual_sr830 import sr830 as VirtualSR830


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.driver = sr830()
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
        self.assertIs(self.driver._resource_manager, self.manager)
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
            {'write_termination': None}, {'output_interface': 2}, {'reset': True},
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
            self.assertIsNone(self.driver._resource_manager)
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
        self.assertIsNone(self.driver._resource_manager)
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
        self.assertIsNone(self.driver._resource_manager)
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

    def test_default_manager_is_retained_but_not_closed(self):
        with patch('sr830.sr830.pyvisa.ResourceManager', return_value=self.manager):
            self.driver.connect('ASRL1::INSTR')
        self.assertIs(self.driver._resource_manager, self.manager)
        self.driver.disconnect()
        self.manager.close.assert_not_called()

    def test_context_manager_and_disconnected_io(self):
        with self.driver:
            self.connect()
        self.resource.close.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, 'not connected'):
            self.driver.reference_frequency

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
        with self.assertRaises(TypeError):
            virtual.connect('ASRL1::INSTR', reset=False)

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

    def test_removed_local_lockout_option_is_rejected_before_opening(self):
        for value in (False, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, 'set local_mode explicitly'):
                    self.connect(local_lockout=value)
                virtual = VirtualSR830()
                with self.assertRaisesRegex(TypeError, 'set local_mode explicitly'):
                    virtual.connect('ASRL1::INSTR', local_lockout=value)
                self.assertFalse(virtual._connected)
        self.manager.open_resource.assert_not_called()

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
        for cls in (sr830, VirtualSR830):
            self.assertEqual(inspect.signature(cls.connect), inspect.signature(sr830.connect))
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
