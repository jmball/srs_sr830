"""Library logging policy checks without hardware."""

from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import warnings

import pyvisa
from pyvisa.constants import InterfaceType
from pyvisa.resources import SerialInstrument

from sr830 import sr830


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.driver = sr830()
        self.resource = Mock(spec=SerialInstrument)
        self.manager = Mock(spec=pyvisa.ResourceManager)
        self.manager.resource_info.return_value = SimpleNamespace(
            interface_type=InterfaceType.asrl
        )
        self.manager.open_resource.return_value = self.resource

    def test_import_preserves_application_logging_and_warning_policy(self):
        script = '''
import logging
import warnings
root = logging.getLogger()
handler = logging.NullHandler()
root.addHandler(handler)
root.setLevel(logging.ERROR)
original_warning_handler = warnings.showwarning
original_handlers = root.handlers[:]
original_filters = warnings.filters[:]
import sr830
import virtual_sr830
assert warnings.showwarning is original_warning_handler
assert root.handlers == original_handlers
assert root.level == logging.ERROR
assert warnings.filters == original_filters
'''
        result = subprocess.run(
            [sys.executable, '-c', script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')

    def test_errors_return_results_without_reporting_them(self):
        self.driver._instr = self.resource
        cases = (
            ([0], []),
            ([1 << 4], ['Interface output buffer is non-empty']),
            ([1 << 2, 1 << 1], ['Battery backup has failed']),
            ([1 << 3, 1 << 0], ['Input or amplifier overload']),
            ([1 << 5, 1 << 2], ['Output queue overflow']),
        )
        for replies, expected in cases:
            with self.subTest(replies=replies):
                self.resource.query.side_effect = [str(value) for value in replies]
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    with warnings.catch_warnings(record=True) as captured:
                        warnings.simplefilter('always')
                        with self.assertNoLogs('sr830', level='DEBUG'):
                            self.assertEqual(self.driver.errors, expected)
                self.assertEqual(stdout.getvalue(), '')
                self.assertEqual(stderr.getvalue(), '')
                self.assertEqual(captured, [])

    def test_status_bits_decode_in_order_and_exclude_non_error_lia_bits(self):
        self.driver._instr = self.resource
        self.resource.query.side_effect = [
            str((1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)),
            str((1 << 1) | (1 << 5)),
            str((1 << 0) | (1 << 2) | (1 << 7)),
            str((1 << 2) | (1 << 4)),
        ]
        self.assertEqual(self.driver.errors, [
            'Interface output buffer is non-empty',
            'Battery backup has failed',
            'GPIB fast data transfer mode aborted',
            'Input or amplifier overload',
            'Output overload',
            'Output queue overflow',
            'Command cannot execute/parameter out of range',
        ])
        self.assertEqual(
            [call.args[0] for call in self.resource.query.call_args_list],
            ['*STB?', 'ERRS?', 'LIAS?', '*ESR?'],
        )

    def test_connection_diagnostics_are_debug_and_do_not_log_measurements(self):
        with self.assertLogs('sr830', level='DEBUG') as captured:
            self.driver.connect('ASRL1::INSTR', resource_manager=self.manager)
            self.resource.query.return_value = '1000'
            self.assertEqual(self.driver.reference_frequency, 1000.0)
            self.driver.disconnect()
        self.assertEqual([record.levelname for record in captured.records], ['DEBUG'] * 4)
        messages = [record.getMessage() for record in captured.records]
        self.assertIn('ASRL1::INSTR', messages[0])
        self.assertIn('RS232', messages[0])
        self.assertIn('initialized', messages[1])
        self.assertIn('Disconnecting', messages[2])
        self.assertIn('disconnected', messages[3])

    def test_propagated_initialization_failure_is_not_logged_as_an_error(self):
        self.resource.write.side_effect = OSError('write failed')
        with self.assertNoLogs('sr830', level='WARNING'):
            with self.assertRaisesRegex(OSError, 'write failed'):
                self.driver.connect('ASRL1::INSTR', resource_manager=self.manager)
        self.assertIsNone(self.driver._instr)
        self.resource.close.assert_called_once()

    def test_serial_binary_warnings_identify_the_caller(self):
        self.driver._instr = self.resource
        self.resource.read_termination = '\r'
        self.resource.read_bytes.return_value = b'\x00' * 4
        for reader in (self.driver.get_binary_buffer_data, self.driver.get_non_norm_buffer_data):
            with self.subTest(reader=reader.__name__):
                self.resource.query.side_effect = ['0', '0']
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter('always')
                    expected_line = inspect.currentframe().f_lineno + 1
                    reader(1, 0, 1)
                self.assertEqual(len(captured), 1)
                self.assertIs(captured[0].category, UserWarning)
                self.assertEqual(captured[0].filename, __file__)
                self.assertEqual(captured[0].lineno, expected_line)
                self.assertIn('binary transfers', str(captured[0].message))


if __name__ == '__main__':
    unittest.main()
