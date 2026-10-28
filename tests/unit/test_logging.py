"""Library logging policy checks without hardware."""

import inspect
import subprocess
import sys
import warnings

import pytest


def test_import_preserves_application_logging_and_warning_policy():
    script = "\nimport logging\nimport warnings\nroot = logging.getLogger()\nhandler = logging.NullHandler()\nroot.addHandler(handler)\nroot.setLevel(logging.ERROR)\noriginal_warning_handler = warnings.showwarning\noriginal_handlers = root.handlers[:]\noriginal_filters = warnings.filters[:]\nimport sr830\nimport virtual_sr830\nassert warnings.showwarning is original_warning_handler\nassert root.handlers == original_handlers\nassert root.level == logging.ERROR\nassert warnings.filters == original_filters\n"
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_error_checks_raise_silently(caplog, driver, resource, query_replies, capsys):
    from sr830 import InstrumentError

    driver._instr = resource
    query_replies["*ESR?"] = "32"
    with warnings.catch_warnings(record=True) as captured:
        with caplog.at_level("DEBUG", logger="sr830"):
            with pytest.raises(InstrumentError, match="illegal command"):
                driver.check_errors()
    assert not caplog.records
    assert captured == []
    assert capsys.readouterr() == ("", "")


def test_connection_diagnostics_are_debug_and_do_not_log_measurements(
    caplog, driver, manager, resource, query_replies
):
    with caplog.at_level("DEBUG", logger="sr830"):
        driver.connect("ASRL1::INSTR", resource_manager=manager)
        query_replies["FREQ?"] = "1000"
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
            frame = inspect.currentframe()
            assert frame is not None
            expected_line = frame.f_lineno + 1
            reader(1, 0, 1)
        assert len(captured) == 1
        assert captured[0].category is UserWarning
        assert captured[0].filename == __file__
        assert captured[0].lineno == expected_line
        assert "binary transfers" in str(captured[0].message)
