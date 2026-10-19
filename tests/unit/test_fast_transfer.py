"""FAST count decoding, lifecycle guards, and cleanup after failures."""

import struct

import pyvisa
import pytest

from sr830 import DataTransferMode


def test_fast_transfer_decodes_signed_pairs_without_query(mock_instrument, resource):
    resource.query.side_effect = ["1", "2"]  # OUTX?, FAST?
    mock_instrument.data_transfer_mode = DataTransferMode.WINDOWS
    mock_instrument.start()
    resource.timeout = 5000
    resource.read_termination = "\n"
    resource.read_bytes.return_value = struct.pack("<hhhh", -30000, 123, 32767, -32768)
    assert mock_instrument.read_fast_data(2, timeout=0.2) == (
        (-30000, 123),
        (32767, -32768),
    )
    assert resource.query.call_count == 2
    assert resource.timeout == 5000
    assert resource.read_termination == "\n"
    with pytest.raises(RuntimeError, match="Stop fast"):
        mock_instrument.idn
    mock_instrument.pause()
    resource.clear.assert_called_once()
    assert not mock_instrument._fast_running


@pytest.mark.parametrize(
    "failure",
    [
        OSError("failed"),
        pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_timeout),
    ],
)
def test_failed_fast_read_stops_and_clears_stream(mock_instrument, resource, failure):
    mock_instrument._fast_running = True
    resource.timeout = 5000
    resource.read_bytes.side_effect = failure
    expected = (
        TimeoutError if isinstance(failure, pyvisa.errors.VisaIOError) else OSError
    )
    with pytest.raises(expected):
        mock_instrument.read_fast_data(1, timeout=0.1)
    resource.write.assert_called_with("PAUS")
    resource.clear.assert_called_once()
    assert resource.timeout == 5000
    assert not mock_instrument._fast_running


def test_failed_fast_cleanup_keeps_text_queries_guarded(mock_instrument, resource):
    mock_instrument._fast_running = True
    resource.clear.side_effect = OSError("clear failed")
    with pytest.raises(OSError):
        mock_instrument.pause()
    with pytest.raises(RuntimeError, match="Stop fast"):
        mock_instrument.idn


def test_short_fast_read_is_an_error_and_stops_acquisition(mock_instrument, resource):
    mock_instrument._fast_running = True
    resource.timeout = 5000
    resource.read_bytes.return_value = b"\0" * 3
    with pytest.raises(OSError, match="Incomplete fast"):
        mock_instrument.read_fast_data(1)
    resource.write.assert_called_with("PAUS")
    resource.clear.assert_called_once()


@pytest.mark.parametrize("command", ["pause", "reset_data_buffers", "reset"])
def test_stopping_fast_mode_discards_queued_bytes(mock_instrument, resource, command):
    mock_instrument._fast_running = True
    getattr(mock_instrument, command)()
    resource.clear.assert_called_once()
    assert not mock_instrument._fast_running


def test_disabling_fast_mode_discards_queued_bytes(mock_instrument, resource):
    mock_instrument._fast_running = True
    mock_instrument.data_transfer_mode = DataTransferMode.OFF
    resource.clear.assert_called_once()
    assert not mock_instrument._fast_running


def test_trigger_tracks_a_fast_stream_without_querying_after_start(
    mock_instrument, resource
):
    resource.query.side_effect = ["1", "2"]  # TSTR?, FAST?
    mock_instrument.trigger()
    assert mock_instrument._fast_running
    mock_instrument.trigger()
    assert resource.query.call_count == 2
    assert resource.write.call_count == 2


def test_fast_mode_rejects_serial_output(mock_instrument, resource):
    resource.query.return_value = "0"
    with pytest.raises(ValueError, match="GPIB"):
        mock_instrument.data_transfer_mode = DataTransferMode.DOS
    resource.write.assert_not_called()


def test_fast_stream_rejects_interface_changes(mock_instrument, resource):
    mock_instrument._fast_running = True
    with pytest.raises(RuntimeError, match="Stop fast"):
        mock_instrument.output_interface = 0
    resource.write.assert_not_called()


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(lambda d: d.get_ascii_buffer_data(1, 0, 1), id="trace-query"),
        pytest.param(
            lambda d: setattr(d, "data_transfer_mode", DataTransferMode.WINDOWS),
            id="change-mode",
        ),
    ],
)
def test_fast_stream_guards_text_queries_and_mode_changes(
    mock_instrument, resource, operation
):
    mock_instrument._fast_running = True
    with pytest.raises(RuntimeError, match="Stop fast"):
        operation(mock_instrument)
    resource.write.assert_not_called()
    resource.query.assert_not_called()
    resource.query_ascii_values.assert_not_called()


def test_starting_an_active_fast_stream_is_idempotent(mock_instrument, resource):
    mock_instrument._fast_running = True
    mock_instrument.start()
    resource.query.assert_not_called()
    resource.write.assert_not_called()


def test_fast_read_requires_a_started_stream(mock_instrument, resource):
    with pytest.raises(RuntimeError, match="Start a fast transfer"):
        mock_instrument.read_fast_data(1)
    resource.read_bytes.assert_not_called()


def test_gpib_fast_reads_restore_framing(driver, gpib_resource):
    resource = gpib_resource
    driver._instr = resource
    driver._fast_running = True
    resource.timeout = 2000
    resource.read_termination = "\n"
    resource.read_bytes.return_value = struct.pack("<hh", 1, -2)
    assert driver.read_fast_data(1) == ((1, -2),)
    assert resource.read_termination == "\n"
    assert resource.timeout == 2000
