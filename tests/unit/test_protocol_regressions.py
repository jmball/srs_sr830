"""Protocol boundaries and recovery paths checked with fake VISA resources."""

import struct
from unittest.mock import patch

import pyvisa
import pytest

from sr830 import DataTransferMode, SerialPollFlag
from tests.cases import SETTING_COMMANDS


@pytest.mark.parametrize("value", [1.5, 1.0, True, "1"])
@pytest.mark.parametrize("name,enum,command", SETTING_COMMANDS)
def test_integer_setting_codes_reject_coercion(
    mock_instrument, resource, name, enum, command, value
):
    with pytest.raises(ValueError):
        setattr(mock_instrument, name, value)
    resource.write.assert_not_called()
    resource.query.assert_not_called()


@pytest.mark.parametrize("value", [1.5, 1.0, True, "1"])
@pytest.mark.parametrize(
    "operation",
    [
        lambda d, v: setattr(d, "harmonic", v),
        lambda d, v: d.save_setup(v),
        lambda d, v: d.recall_setup(v),
        lambda d, v: d.set_enable_register("error", v),
        lambda d, v: d.get_enable_register("error", v),
        lambda d, v: d.get_status_byte("error", v),
        lambda d, v: d.get_ascii_buffer_data(1, v, 1),
        lambda d, v: d.get_ascii_buffer_data(1, 0, v),
    ],
)
def test_integer_arguments_reject_coercion(mock_instrument, resource, operation, value):
    with pytest.raises(ValueError):
        operation(mock_instrument, value)
    resource.write.assert_not_called()
    resource.query.assert_not_called()


@pytest.mark.parametrize("bits", [5, 6, 7, 8.0, True])
def test_serial_requires_eight_bits_before_open(connect, manager, bits):
    with pytest.raises(ValueError, match="data_bits=8"):
        connect(data_bits=bits)
    manager.open_resource.assert_not_called()


def test_output_interface_write_failure_restores_framing(connect, driver, resource):
    connect()
    resource.write.side_effect = OSError("failed OUTX")
    with pytest.raises(OSError, match="failed OUTX"):
        driver.output_interface = 1
    assert resource.read_termination == "\r"


@pytest.mark.parametrize(
    "fields", [[], [""], ["1", ""], ["1", "2", "3", ""], ["bad", "2"]]
)
def test_ascii_requires_exact_valid_sample_count(mock_instrument, resource, fields):
    resource.query.side_effect = ["1", "2"]
    resource.query_ascii_values.return_value = fields
    with pytest.raises(OSError):
        mock_instrument.get_ascii_buffer_data(1, 0, 2, resume=True)
    assert [c.args[0] for c in resource.write.call_args_list] == ["PAUS"]


@pytest.mark.parametrize(
    "reader", ["get_binary_buffer_data", "get_non_norm_buffer_data"]
)
def test_short_binary_response_leaves_loop_paused_and_restores_framing(
    mock_instrument, resource, reader
):
    resource.read_termination = "\n"
    resource.query.side_effect = ["1", "2", "1"]
    resource.read_bytes.return_value = b"\0" * 4
    with pytest.raises(OSError, match="Incomplete"):
        getattr(mock_instrument, reader)(1, 0, 2, resume=True)
    assert resource.read_termination == "\n"
    assert "STRT" not in [c.args[0] for c in resource.write.call_args_list]


@pytest.mark.parametrize("resume", [False, True])
def test_successful_loop_read_has_explicit_resume_policy(
    mock_instrument, resource, resume
):
    resource.query.side_effect = ["1", "1", "0"]
    resource.query_ascii_values.return_value = ["2", ""]
    assert mock_instrument.get_ascii_buffer_data(1, 0, 1, resume=resume) == (2.0,)
    commands = [c.args[0] for c in resource.write.call_args_list]
    assert commands == (["PAUS", "STRT"] if resume else ["PAUS"])


@pytest.mark.parametrize("start,bins", [(16382, 2), (-1, 1), (0, 0)])
def test_impossible_trace_ranges_are_rejected_before_io(
    mock_instrument, resource, start, bins
):
    with pytest.raises(ValueError):
        mock_instrument.get_ascii_buffer_data(1, start, bins)
    resource.query.assert_not_called()


def test_trace_range_cannot_exceed_acquired_samples(mock_instrument, resource):
    resource.query.side_effect = ["1", "2"]
    with pytest.raises(ValueError, match="stored"):
        mock_instrument.get_ascii_buffer_data(1, 1, 2)
    resource.query_ascii_values.assert_not_called()


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


def test_native_ready_poll_sends_no_query_and_restores_timeout(
    mock_instrument, resource
):
    resource.timeout = 2000
    resource.read_stb.side_effect = [0, int(SerialPollFlag.NO_COMMAND_IN_PROGRESS)]
    mock_instrument.wait_until_ready(timeout=0.1, poll_interval=0.001)
    resource.query.assert_not_called()
    assert resource.timeout == 2000


def test_ready_uses_queued_barrier_when_native_poll_is_unsupported(
    mock_instrument, resource
):
    resource.timeout = 2000
    resource.read_stb.side_effect = NotImplementedError
    resource.query.return_value = "2"
    mock_instrument.wait_until_ready(timeout=0.1)
    resource.query.assert_called_once_with("*STB?")
    assert resource.timeout == 2000


def test_ready_timeout_is_bounded_and_restores_timeout(mock_instrument, resource):
    resource.timeout = 2000
    resource.read_stb.return_value = 0
    with pytest.raises(TimeoutError):
        mock_instrument.wait_until_ready(timeout=0.003, poll_interval=0.001)
    assert resource.timeout == 2000


def test_settling_estimate_respects_budget(mock_instrument, resource):
    resource.timeout = 2000
    resource.read_stb.return_value = 2
    resource.query.return_value = "8"  # 100 ms
    with patch("sr830.sr830.time.sleep") as sleep:
        mock_instrument.wait_for_settling(timeout=2, time_constants=10)
        sleep.assert_called_once_with(1.0)
    with pytest.raises(TimeoutError):
        mock_instrument.wait_for_settling(timeout=0.1)
    assert resource.timeout == 2000


@pytest.mark.parametrize(
    "reader_name,raw",
    [
        ("get_binary_buffer_data", struct.pack("<f", 1.25)),
        ("get_non_norm_buffer_data", struct.pack("<hh", 10, 124)),
    ],
)
def test_binary_loop_read_resumes_with_start_command(
    mock_instrument, resource, reader_name, raw
):
    resource.query.side_effect = ["1", "1", "1", "0"]
    resource.read_bytes.return_value = raw
    getattr(mock_instrument, reader_name)(1, 0, 1, resume=True)
    assert [c.args[0] for c in resource.write.call_args_list][-1] == "STRT"
    assert not any(c.args[0].startswith("SEND") for c in resource.write.call_args_list)


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


@pytest.mark.parametrize(
    "code",
    [
        pyvisa.constants.StatusCode.error_nonsupported_operation,
        pyvisa.constants.StatusCode.error_nonimplemented_operation,
    ],
)
def test_native_poll_reports_unsupported_visa_backends(mock_instrument, resource, code):
    resource.read_stb.side_effect = pyvisa.errors.VisaIOError(code)
    with pytest.raises(NotImplementedError, match="native status polling"):
        mock_instrument.serial_poll()


def test_ready_barrier_timeout_is_translated_and_restores_timeout(
    mock_instrument, resource
):
    resource.timeout = 2000
    resource.read_stb.side_effect = NotImplementedError
    resource.query.side_effect = pyvisa.errors.VisaIOError(
        pyvisa.constants.StatusCode.error_timeout
    )
    with pytest.raises(TimeoutError, match="command completion"):
        mock_instrument.wait_until_ready(timeout=0.1)
    assert resource.timeout == 2000


def test_settling_query_timeout_is_translated_and_restores_timeout(
    mock_instrument, resource
):
    resource.timeout = 2000
    resource.read_stb.return_value = 2
    resource.query.side_effect = pyvisa.errors.VisaIOError(
        pyvisa.constants.StatusCode.error_timeout
    )
    with pytest.raises(TimeoutError, match="time constant"):
        mock_instrument.wait_for_settling(timeout=0.1)
    assert resource.timeout == 2000


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


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_waits_reject_invalid_timeouts_without_io(mock_instrument, resource, timeout):
    for wait in (mock_instrument.wait_until_ready, mock_instrument.wait_for_settling):
        with pytest.raises(ValueError):
            wait(timeout=timeout)
    resource.query.assert_not_called()
    resource.read_stb.assert_not_called()
