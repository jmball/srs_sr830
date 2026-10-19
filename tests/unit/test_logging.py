"""Library logging policy checks without hardware."""

import pytest
from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import subprocess
import sys
import warnings


def test_import_preserves_application_logging_and_warning_policy():
    script = "\nimport logging\nimport warnings\nroot = logging.getLogger()\nhandler = logging.NullHandler()\nroot.addHandler(handler)\nroot.setLevel(logging.ERROR)\noriginal_warning_handler = warnings.showwarning\noriginal_handlers = root.handlers[:]\noriginal_filters = warnings.filters[:]\nimport sr830\nimport virtual_sr830\nassert warnings.showwarning is original_warning_handler\nassert root.handlers == original_handlers\nassert root.level == logging.ERROR\nassert warnings.filters == original_filters\n"
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_errors_return_results_without_reporting_them(caplog, driver, resource):
    driver._instr = resource
    cases = (
        ([0], []),
        ([1 << 4], ["Interface output buffer is non-empty"]),
        ([1 << 2, 1 << 1], ["Battery backup has failed"]),
        ([1 << 3, 1 << 0], ["Input or amplifier overload"]),
        ([1 << 5, 1 << 2], ["Output queue overflow"]),
    )
    for replies, expected in cases:
        resource.query.side_effect = [str(value) for value in replies]
        stdout, stderr = (io.StringIO(), io.StringIO())
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                with caplog.at_level("DEBUG", logger="sr830"):
                    assert driver.errors == expected
                assert not caplog.records
        assert stdout.getvalue() == ""
        assert stderr.getvalue() == ""
        assert captured == []


def test_status_bits_decode_in_order_and_exclude_non_error_lia_bits(driver, resource):
    driver._instr = resource
    resource.query.side_effect = [
        str(1 << 2 | 1 << 3 | 1 << 4 | 1 << 5),
        str(1 << 1 | 1 << 5),
        str(1 << 0 | 1 << 2 | 1 << 7),
        str(1 << 2 | 1 << 4),
    ]
    assert driver.errors == [
        "Interface output buffer is non-empty",
        "Battery backup has failed",
        "GPIB fast data transfer mode aborted",
        "Input or amplifier overload",
        "Output overload",
        "Output queue overflow",
        "Command cannot execute/parameter out of range",
    ]
    assert [call.args[0] for call in resource.query.call_args_list] == [
        "*STB?",
        "ERRS?",
        "LIAS?",
        "*ESR?",
    ]


def test_connection_diagnostics_are_debug_and_do_not_log_measurements(
    caplog, driver, manager, resource
):
    with caplog.at_level("DEBUG", logger="sr830"):
        driver.connect("ASRL1::INSTR", resource_manager=manager)
        resource.query.return_value = "1000"
        assert driver.reference_frequency == 1000.0
        driver.disconnect()
    assert [record.levelname for record in caplog.records] == ["DEBUG"] * 4
    messages = [record.getMessage() for record in caplog.records]
    assert "ASRL1::INSTR" in messages[0]
    assert "RS232" in messages[0]
    assert "initialized" in messages[1]
    assert "Disconnecting" in messages[2]
    assert "disconnected" in messages[3]


def test_propagated_initialization_failure_is_not_logged_as_an_error(
    caplog, driver, manager, resource
):
    resource.write.side_effect = OSError("write failed")
    with caplog.at_level("WARNING", logger="sr830"):
        with pytest.raises(OSError, match="write failed"):
            driver.connect("ASRL1::INSTR", resource_manager=manager)
    assert not caplog.records
    assert driver._instr is None
    resource.close.assert_called_once()


def test_serial_binary_warnings_identify_the_caller(driver, resource, query_replies):
    driver._instr = resource
    resource.read_termination = "\r"
    resource.read_bytes.return_value = b"\x00" * 4
    for reader in (driver.get_binary_buffer_data, driver.get_non_norm_buffer_data):
        query_replies.update({"SEND?": "0", "SPTS?": "1", "OUTX?": "0"})
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            expected_line = inspect.currentframe().f_lineno + 1
            reader(1, 0, 1)
        assert len(captured) == 1
        assert captured[0].category is UserWarning
        assert captured[0].filename == __file__
        assert captured[0].lineno == expected_line
        assert "binary transfers" in str(captured[0].message)
