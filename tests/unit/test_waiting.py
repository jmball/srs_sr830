"""Completion budgets, slope-based settling estimates, and VISA error handling."""

from types import SimpleNamespace

import pytest
import pyvisa
from pyvisa.constants import StatusCode

from sr830 import SerialPollFlag
from tests.support import ManualClock

pytestmark = pytest.mark.usefixtures("clock")


@pytest.fixture
def clock(monkeypatch):
    clock = ManualClock()
    monkeypatch.setattr(
        "sr830.sr830.time", SimpleNamespace(monotonic=clock, sleep=clock.advance)
    )
    return clock


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


@pytest.mark.parametrize("slope,delay", [(0, 0.5), (1, 0.7), (2, 0.9), (3, 1.0)])
def test_settling_uses_manual_slope_recommendation(
    mock_instrument, resource, query_replies, clock, slope, delay
):
    resource.timeout = 2000
    query_replies.update({"OFSL?": str(slope), "OFLT?": "8"})  # 100 ms
    mock_instrument.wait_for_settling()
    assert clock.now == pytest.approx(delay)
    resource.read_stb.assert_not_called()
    assert resource.timeout == 2000


def test_settling_override_skips_slope_query(
    mock_instrument, resource, query_replies, clock
):
    query_replies["OFLT?"] = "11"  # 3 s
    mock_instrument.wait_for_settling(time_constants=2.5)
    assert clock.now == 7.5
    assert all(call.args[0] != "OFSL?" for call in resource.query.call_args_list)


def test_settling_has_no_overall_timeout(mock_instrument, query_replies, clock):
    query_replies.update({"OFSL?": "3", "OFLT?": "19"})  # 24 dB/oct, 30 ks
    mock_instrument.wait_for_settling()
    assert clock.now == 300000


@pytest.mark.parametrize("time_constants", [0, -1, float("nan"), float("inf")])
def test_settling_rejects_invalid_overrides_before_io(
    mock_instrument, resource, time_constants
):
    with pytest.raises(ValueError, match="finite and positive"):
        mock_instrument.wait_for_settling(time_constants=time_constants)
    resource.query.assert_not_called()


def test_settling_rejects_overflow_before_sleep(mock_instrument, query_replies, clock):
    query_replies["OFLT?"] = "19"
    with pytest.raises(ValueError, match="delay must be finite"):
        mock_instrument.wait_for_settling(time_constants=1e308)
    assert clock.now == 0


@pytest.mark.parametrize(
    "code",
    [
        StatusCode.error_nonsupported_operation,
        StatusCode.error_nonimplemented_operation,
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
    resource.query.side_effect = pyvisa.errors.VisaIOError(StatusCode.error_timeout)
    with pytest.raises(TimeoutError, match="command completion"):
        mock_instrument.wait_until_ready(timeout=0.1)
    assert resource.timeout == 2000


def test_settling_preserves_visa_query_timeout(mock_instrument, resource, clock):
    resource.timeout = 2000
    failure = pyvisa.errors.VisaIOError(StatusCode.error_timeout)
    resource.query.side_effect = failure
    with pytest.raises(pyvisa.errors.VisaIOError) as caught:
        mock_instrument.wait_for_settling()
    assert caught.value is failure
    assert resource.timeout == 2000
    assert clock.now == 0


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_waits_reject_invalid_timeouts_without_io(mock_instrument, resource, timeout):
    with pytest.raises(ValueError):
        mock_instrument.wait_until_ready(timeout=timeout)
    resource.query.assert_not_called()
    resource.read_stb.assert_not_called()


@pytest.mark.parametrize(
    "operation", ["serial_poll", "wait_until_ready", "wait_for_settling"]
)
def test_non_timeout_visa_errors_are_preserved(mock_instrument, resource, operation):
    resource.timeout = 2000
    failure = pyvisa.errors.VisaIOError(StatusCode.error_system_error)
    if operation == "wait_for_settling":
        resource.read_stb.return_value = int(SerialPollFlag.NO_COMMAND_IN_PROGRESS)
        resource.query.side_effect = failure
    else:
        resource.read_stb.side_effect = failure
    with pytest.raises(pyvisa.errors.VisaIOError) as caught:
        getattr(mock_instrument, operation)()
    assert caught.value is failure
    assert resource.timeout == 2000
