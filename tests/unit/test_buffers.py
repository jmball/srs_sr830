"""Trace range checks, decoding, pause policy, and framing recovery."""

import struct

from pyvisa.constants import SerialTermination

import pytest

from sr830 import Channel


@pytest.mark.parametrize(
    "fields", [[], [""], ["1", ""], ["1", "2", "3", ""], ["bad", "2"]]
)
def test_ascii_requires_exact_valid_sample_count(
    mock_instrument, resource, query_replies, fields
):
    query_replies.update({"SEND?": "1", "SPTS?": "2"})
    resource.query_ascii_values.return_value = fields
    with pytest.raises(OSError):
        mock_instrument.get_ascii_buffer_data(1, 0, 2, resume=True)
    assert [c.args[0] for c in resource.write.call_args_list] == ["PAUS"]


@pytest.mark.parametrize(
    "reader", ["get_binary_buffer_data", "get_non_norm_buffer_data"]
)
def test_short_binary_response_leaves_loop_paused_and_restores_framing(
    mock_instrument, resource, query_replies, reader
):
    resource.read_termination = "\n"
    query_replies.update({"SEND?": "1", "SPTS?": "2", "OUTX?": "1"})
    resource.read_bytes.return_value = b"\0" * 4
    with pytest.raises(OSError, match="Incomplete"):
        getattr(mock_instrument, reader)(1, 0, 2, resume=True)
    assert resource.read_termination == "\n"
    assert "STRT" not in [c.args[0] for c in resource.write.call_args_list]


@pytest.mark.parametrize("resume", [False, True], ids=["leave-paused", "resume"])
@pytest.mark.parametrize(
    "reader_name,raw",
    [
        pytest.param("get_ascii_buffer_data", None, id="ascii"),
        pytest.param("get_binary_buffer_data", struct.pack("<f", 1.25), id="ieee"),
        pytest.param(
            "get_non_norm_buffer_data", struct.pack("<hh", 5, 122), id="mantissa"
        ),
    ],
)
def test_loop_read_has_explicit_resume_policy(
    mock_instrument, resource, query_replies, reader_name, raw, resume
):
    query_replies.update({"SEND?": "1", "SPTS?": "1", "OUTX?": "1", "FAST?": "0"})
    resource.query_ascii_values.return_value = ["1.25", ""]
    resource.read_bytes.return_value = raw
    values = getattr(mock_instrument, reader_name)(Channel.CH2, 0, 1, resume=resume)
    assert values == (1.25,)
    commands = [call.args[0] for call in resource.write.call_args_list]
    assert commands[0] == "PAUS"
    assert (commands[-1] == "STRT") is resume
    assert not any(command.startswith("SEND") for command in commands)


@pytest.mark.parametrize("start,bins", [(16382, 2), (-1, 1), (0, 0)])
def test_impossible_trace_ranges_are_rejected_before_io(
    mock_instrument, resource, start, bins
):
    with pytest.raises(ValueError):
        mock_instrument.get_ascii_buffer_data(1, start, bins)
    resource.query.assert_not_called()


def test_trace_range_cannot_exceed_acquired_samples(
    mock_instrument, resource, query_replies
):
    query_replies.update({"SEND?": "1", "SPTS?": "2"})
    with pytest.raises(ValueError, match="stored"):
        mock_instrument.get_ascii_buffer_data(1, 1, 2)
    resource.query_ascii_values.assert_not_called()


@pytest.mark.parametrize(
    "reader",
    ["get_ascii_buffer_data", "get_binary_buffer_data", "get_non_norm_buffer_data"],
)
@pytest.mark.parametrize("channel", [0, 3])
def test_all_readers_reject_invalid_channels_before_io(
    mock_instrument, resource, reader, channel
):
    with pytest.raises(ValueError):
        getattr(mock_instrument, reader)(channel, 0, 1)
    resource.query.assert_not_called()
    resource.write.assert_not_called()


def test_gpib_binary_reads_restore_framing_on_success_and_failure(
    driver, gpib_resource
):
    resource = gpib_resource
    driver._instr = resource
    resource.read_termination = "\n"
    resource.read_bytes.return_value = struct.pack("<f", 1.25)
    assert driver._read_buffer_bytes("TRCB? 1,0,1", 4) == struct.pack("<f", 1.25)
    assert resource.read_termination == "\n"
    resource.read_bytes.side_effect = OSError("read failed")
    with pytest.raises(OSError, match="read failed"):
        driver._read_buffer_bytes("TRCB? 1,0,1", 4)
    assert resource.read_termination == "\n"


def test_ascii_buffer_uses_guarded_query_and_preserves_parsing(
    connect, driver, resource, query_replies
):
    connect()
    query_replies.update({"SEND?": "0", "SPTS?": "2"})
    resource.query_ascii_values.return_value = ["1.25", "-2.5", ""]
    assert driver.get_ascii_buffer_data(1, 0, 2) == (1.25, -2.5)
    assert resource.query_ascii_values.call_args.args == ("TRCA? 1,0,2",)


@pytest.mark.parametrize(
    "reader_name,command,raw,expected",
    [
        pytest.param(
            "get_binary_buffer_data", "TRCB?", bytes([13, 10, 128, 63]),
            struct.unpack("<f", bytes([13, 10, 128, 63])), id="ieee",
        ),
        pytest.param(
            "get_non_norm_buffer_data", "TRCL?", struct.pack("<hh", 10, 124),
            (10.0,), id="mantissa",
        ),
    ],
)
def test_serial_binary_reads_ignore_text_terminators_and_restore_framing(
    connect, driver, resource, query_replies, reader_name, command, raw, expected
):
    connect()
    original_end = resource.end_input

    def read(size, **kwargs):
        assert size == 4
        assert kwargs == {"break_on_termchar": False}
        assert resource.read_termination is None
        assert resource.end_input == SerialTermination.none
        return raw

    resource.read_bytes.side_effect = read
    query_replies.update({"SEND?": "0", "SPTS?": "1", "OUTX?": "0"})
    with pytest.warns(UserWarning, match="binary transfers"):
        assert getattr(driver, reader_name)(1, 0, 1) == expected
    resource.write.assert_any_call(f"{command} 1,0,1")
    assert resource.read_termination == "\r"
    assert resource.end_input == original_end


def test_binary_read_failure_restores_text_framing(
    connect, driver, resource, query_replies
):
    connect()
    original_end = resource.end_input
    query_replies.update({"SEND?": "1", "SPTS?": "1", "OUTX?": "0"})
    resource.read_bytes.side_effect = OSError("read failed")
    with pytest.warns(UserWarning, match="binary transfers"):
        with pytest.raises(OSError, match="read failed"):
            driver.get_binary_buffer_data(1, 0, 1)
    assert resource.read_termination == "\r"
    assert resource.end_input == original_end
