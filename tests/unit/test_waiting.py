"""Completion and settling budgets, backend polling, and timeout restoration."""

from types import SimpleNamespace

import pyvisa
import pytest

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


def test_settling_estimate_respects_budget(mock_instrument, resource, clock):
    resource.timeout = 2000
    resource.read_stb.return_value = 2
    resource.query.return_value = "8"  # 100 ms
    mock_instrument.wait_for_settling(timeout=2, time_constants=10)
    assert clock.now == 1.0
    with pytest.raises(TimeoutError):
        mock_instrument.wait_for_settling(timeout=0.1)
    assert resource.timeout == 2000


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


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_waits_reject_invalid_timeouts_without_io(mock_instrument, resource, timeout):
    for wait in (mock_instrument.wait_until_ready, mock_instrument.wait_for_settling):
        with pytest.raises(ValueError):
            wait(timeout=timeout)
    resource.query.assert_not_called()
    resource.read_stb.assert_not_called()


@pytest.mark.parametrize(
    "operation", ["serial_poll", "wait_until_ready", "wait_for_settling"]
)
def test_non_timeout_visa_errors_are_preserved(mock_instrument, resource, operation):
    resource.timeout = 2000
    failure = pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_system_error)
    if operation == "wait_for_settling":
        resource.read_stb.return_value = int(SerialPollFlag.NO_COMMAND_IN_PROGRESS)
        resource.query.side_effect = failure
    else:
        resource.read_stb.side_effect = failure
    with pytest.raises(pyvisa.errors.VisaIOError) as caught:
        getattr(mock_instrument, operation)()
    assert caught.value is failure
    assert resource.timeout == 2000


def test_settling_budget_includes_command_completion(mock_instrument, resource, clock):
    resource.timeout = 2000

    def finish_command():
        clock.advance(1)
        return int(SerialPollFlag.NO_COMMAND_IN_PROGRESS)

    resource.read_stb.side_effect = finish_command
    with pytest.raises(TimeoutError, match="Settling timeout expired"):
        mock_instrument.wait_for_settling(timeout=1)
    resource.query.assert_not_called()
    assert resource.timeout == 2000
