"""Native limits and configuration-dependent capabilities."""

import pytest

from sr830 import SR830, settings
from virtual_sr830 import VirtualSR830


@pytest.mark.parametrize("driver_type", [SR830, VirtualSR830])
def test_native_limits_are_read_only_and_need_no_connection(driver_type):
    instrument = driver_type()
    assert instrument.buffer_capacity == 16383
    assert instrument.harmonic_limits == (1, 19999)
    for name in ("buffer_capacity", "harmonic_limits"):
        with pytest.raises(AttributeError):
            setattr(instrument, name, 0)


@pytest.mark.parametrize("code,available", [(9, True), (10, True), (11, False)])
def test_auto_gain_checks_actual_time_constant(
    mock_instrument, resource, query_replies, code, available
):
    query_replies["OFLT?"] = str(code)
    assert mock_instrument.auto_gain_available is available
    if available:
        mock_instrument.auto_gain()
        resource.write.assert_called_once_with("AGAN")
    else:
        with pytest.raises(RuntimeError, match="1 second or less"):
            mock_instrument.auto_gain()
        resource.write.assert_not_called()


def test_disabled_synchronous_filter_needs_no_frequency_queries(
    mock_instrument, resource, query_replies
):
    query_replies["SYNC?"] = "0"
    assert mock_instrument.synchronous_filter_active is False
    commands = [call.args[0] for call in resource.query.call_args_list]
    assert "FREQ?" not in commands
    assert "HARM?" not in commands


@pytest.mark.parametrize(
    "frequency,harmonic,active",
    [
        (199.20, 1, True),
        (199.21, 1, None),
        (203.12, 1, None),
        (203.13, 1, False),
        (100, 2, None),
        (100, 3, False),
        (0, 1, None),
        (float("nan"), 1, None),
    ],
)
def test_hardware_synchronous_activity_uses_detection_frequency(
    mock_instrument, query_replies, frequency, harmonic, active
):
    query_replies.update(
        {"SYNC?": "1", "FREQ?": str(frequency), "HARM?": str(harmonic)}
    )
    assert mock_instrument.synchronous_filter_active is active


def test_hardware_reads_cannot_establish_hysteresis_history(
    mock_instrument, query_replies
):
    query_replies.update({"SYNC?": "1", "FREQ?": "100", "HARM?": "1"})
    assert mock_instrument.synchronous_filter_active is True
    query_replies["FREQ?"] = "200"
    assert mock_instrument.synchronous_filter_active is None


def test_simulated_synchronous_filter_preserves_known_history(simulation):
    simulation.sync_filter_status = settings.SynchronousFilter.BELOW_200_HZ
    simulation.reference_frequency = 100
    simulation.reference_frequency = 200
    assert simulation.synchronous_filter_active is True
    simulation.reference_frequency = 300
    simulation.reference_frequency = 200
    assert simulation.synchronous_filter_active is False
    simulation.sync_filter_status = settings.SynchronousFilter.OFF
    simulation.reference_frequency = 100
    assert simulation.synchronous_filter_active is False
    simulation.sync_filter_status = settings.SynchronousFilter.BELOW_200_HZ
    assert simulation.synchronous_filter_active is True
    simulation.reset()
    assert simulation.synchronous_filter_active is False


def test_simulated_synchronous_filter_loses_history_when_reference_is_unavailable(
    simulation,
):
    simulation.set_external_reference(100)
    simulation.reference_source = settings.ReferenceSource.EXTERNAL
    simulation.sync_filter_status = settings.SynchronousFilter.BELOW_200_HZ
    assert simulation.synchronous_filter_active is True
    simulation.set_external_reference(200, locked=False)
    assert simulation.synchronous_filter_active is None
    simulation.set_external_reference(200)
    assert simulation.synchronous_filter_active is None
    simulation.set_external_reference(100)
    assert simulation.synchronous_filter_active is True
