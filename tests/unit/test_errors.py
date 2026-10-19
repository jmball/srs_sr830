"""Fault policy and safe diagnostics at transport/measurement boundaries."""

import struct

import pyvisa
import pytest
from pyvisa.constants import InterfaceType, StatusCode

from sr830 import InstrumentError, settings
from virtual_sr830 import InstrumentError as VirtualInstrumentError


def timeout_error():
    return pyvisa.errors.VisaIOError(StatusCode.error_timeout)


def test_write_checks_direct_registers_and_decodes_faults(
    mock_instrument, resource, query_replies
):
    # No *STB? or enable mask participates in fault detection.
    query_replies.update({"*ESR?": "48", "ERRS?": "128"})
    with pytest.raises(InstrumentError) as caught:
        mock_instrument.reference_frequency = 123
    assert VirtualInstrumentError is InstrumentError
    assert str(caught.value) == (
        "Command cannot execute/parameter out of range; "
        "Received illegal command; Internal math error"
    )
    assert [call.args[0] for call in resource.method_calls] == [
        "FREQ 123",
        "*ESR?",
        "ERRS?",
    ]


def test_successful_query_checks_faults_after_reading_response(
    mock_instrument, resource, query_replies
):
    query_replies.update({"FREQ?": "123", "ERRS?": "4"})
    with pytest.raises(InstrumentError, match="RAM memory"):
        mock_instrument.reference_frequency
    assert [call.args[0] for call in resource.query.call_args_list] == [
        "FREQ?",
        "*ESR?",
        "ERRS?",
    ]


def test_ordinary_events_are_not_errors_and_explicit_reads_do_not_consume_other_registers(
    simulation,
):
    simulation.inject_status("standard_event", settings.StandardEventFlag.POWER_ON)
    simulation.inject_status(
        "lia_status",
        settings.LiaStatusFlag.TRIGGER | settings.LiaStatusFlag.TIME_CONSTANT_CHANGED,
    )
    simulation.check_errors()
    simulation.check_measurement_status()
    assert simulation.get_status_byte("standard_event") == 0
    simulation.inject_status("error", settings.ErrorFlag.RAM_ERROR)
    assert simulation.get_status_byte("lia_status") == 0
    assert simulation.get_status_byte("error") == settings.ErrorFlag.RAM_ERROR
    simulation.check_errors()  # The explicit raw read already consumed the fault.


def test_disabled_enable_masks_do_not_hide_faults(simulation):
    simulation.set_enable_register("standard_event", 0)
    simulation.set_enable_register("error", 0)
    simulation.inject_status(
        "standard_event", settings.StandardEventFlag.EXECUTION_ERROR
    )
    assert not simulation.serial_poll() & settings.SerialPollFlag.STANDARD_EVENT
    with pytest.raises(InstrumentError, match="cannot execute"):
        simulation.check_errors()
    simulation.check_errors()  # Latched fault was cleared by the first check.


def test_configuration_can_fix_a_measurement_fault(simulation):
    simulation.set_signal(0.01, settle=True)
    simulation.sensitivity = settings.Sensitivity.x1m
    simulation.sensitivity = settings.Sensitivity.x1
    # Configuration left the old overload latch available to the measurement.
    with pytest.raises(InstrumentError, match="overload"):
        simulation.measure(settings.MeasurementParameter.X)
    assert simulation.measure(settings.MeasurementParameter.X) == 0.01
    simulation.set_external_reference(42, locked=False)
    with pytest.raises(InstrumentError, match="Reference unlock"):
        simulation.check_measurement_status()


@pytest.mark.parametrize("command", ["INVALID", "FREQ 100"])
def test_simulated_rejected_writes_raise_instrument_error(simulation, command):
    simulation.reference_source = settings.ReferenceSource.EXTERNAL
    with pytest.raises(InstrumentError):
        simulation._write(command)


def test_simulated_bad_query_raises_instrument_error_chained_from_timeout(simulation):
    with pytest.raises(InstrumentError, match="illegal command") as caught:
        simulation._query("INVALID?")
    assert isinstance(caught.value.__cause__, pyvisa.errors.VisaIOError)
    assert simulation.idn


def test_initialization_fault_closes_resource_before_publishing_connection(
    connect, driver, resource, query_replies
):
    query_replies["*ESR?"] = "32"
    with pytest.raises(InstrumentError, match="illegal command"):
        connect()
    assert driver._instr is None
    resource.close.assert_called_once()


@pytest.mark.parametrize("diagnostic", ["fault", "no-fault", "timeout", "malformed"])
def test_native_gpib_timeout_recovery_preserves_or_explains_original_failure(
    driver, gpib_resource, diagnostic
):
    resource = gpib_resource
    driver._instr = resource
    resource.timeout = 5000
    failure = timeout_error()

    def query(command):
        if command == "FREQ?":
            raise failure
        # All recovery I/O runs with a short timeout, restored afterwards.
        assert resource.timeout == 1000
        if diagnostic == "timeout":
            raise timeout_error()
        if diagnostic == "malformed":
            return "delayed original response"
        return "32" if diagnostic == "fault" and command == "*ESR?" else "0"

    resource.query.side_effect = query
    expected = InstrumentError if diagnostic == "fault" else pyvisa.errors.VisaIOError
    with pytest.raises(expected) as caught:
        driver.reference_frequency
    if diagnostic == "fault":
        assert caught.value.__cause__ is failure
    else:
        assert caught.value is failure
    resource.clear.assert_called_once()
    assert resource.timeout == 5000
    if diagnostic in ("timeout", "malformed"):
        with pytest.raises(RuntimeError, match="reconnect"):
            driver.idn
    else:
        resource.query.side_effect = lambda command: (
            "SR830" if command == "*IDN?" else "0"
        )
        assert driver.idn == "SR830"


@pytest.mark.parametrize("interface", [InterfaceType.asrl, InterfaceType.tcpip])
def test_ambiguous_timeout_does_not_misread_a_delayed_response(
    mock_instrument, resource, interface
):
    resource.interface_type = interface
    resource.timeout = 5000
    failure = timeout_error()
    resource.query.side_effect = failure
    with pytest.raises(pyvisa.errors.VisaIOError) as caught:
        mock_instrument.idn
    assert caught.value is failure
    resource.query.assert_called_once_with("*IDN?")
    resource.clear.assert_not_called()
    assert resource.timeout == 5000
    with pytest.raises(RuntimeError, match="reconnect"):
        mock_instrument.idn
    with pytest.raises(RuntimeError, match="reconnect"):
        mock_instrument.reference_frequency = 100


def test_failed_device_clear_preserves_timeout_and_requires_reconnect(
    driver, gpib_resource
):
    driver._instr = gpib_resource
    gpib_resource.timeout = 5000
    failure = timeout_error()
    gpib_resource.query.side_effect = failure
    gpib_resource.clear.side_effect = OSError("clear failed")
    with pytest.raises(pyvisa.errors.VisaIOError) as caught:
        driver.idn
    assert caught.value is failure
    assert gpib_resource.timeout == 5000
    gpib_resource.query.assert_called_once_with("*IDN?")


def test_confirmed_fault_survives_later_diagnostic_failure(mock_instrument, resource):
    resource.query.side_effect = ["32", timeout_error()]
    with pytest.raises(InstrumentError, match="illegal command") as caught:
        mock_instrument.check_errors()
    assert isinstance(caught.value.__cause__, pyvisa.errors.VisaIOError)
    with pytest.raises(RuntimeError, match="reconnect"):
        mock_instrument.idn


def test_binary_diagnostics_wait_for_complete_read_and_restored_framing(
    mock_instrument, resource
):
    resource.read_termination = "\r"
    resource.end_input = pyvisa.constants.SerialTermination.termination_char
    raw = struct.pack("<f", 1.25)
    resource.read_bytes.return_value = raw

    def diagnostic(command):
        resource.read_bytes.assert_called_once_with(4, break_on_termchar=False)
        assert resource.read_termination == "\r"
        assert resource.end_input == pyvisa.constants.SerialTermination.termination_char
        return "128" if command == "ERRS?" else "0"

    resource.query.side_effect = diagnostic
    with pytest.raises(InstrumentError, match="Internal math"):
        mock_instrument._read_buffer_bytes("TRCB? 1,0,1", 4)


def test_ascii_transfer_fault_is_not_hidden_by_a_valid_response(
    mock_instrument, resource, query_replies
):
    resource.query_ascii_values.return_value = ["1.25", ""]
    query_replies["*ESR?"] = "4"
    with pytest.raises(InstrumentError, match="Output queue overflow"):
        mock_instrument._query_ascii_values("TRCA? 1,0,1")


def test_failed_fast_read_reports_confirmed_instrument_fault(
    mock_instrument, resource, query_replies
):
    mock_instrument._fast_running = True
    resource.timeout = 5000
    failure = timeout_error()
    resource.read_bytes.side_effect = failure

    def diagnostic(command):
        resource.clear.assert_called_once()
        assert not mock_instrument._fast_running
        return "32" if command == "ERRS?" else "0"

    resource.query.side_effect = diagnostic
    with pytest.raises(InstrumentError, match="fast data transfer") as caught:
        mock_instrument.read_fast_data(1)
    assert caught.value.__cause__ is failure
    assert resource.timeout == 5000


@pytest.mark.parametrize("transfer", ["ascii", "binary"])
def test_buffer_timeout_recovers_before_reading_error_registers(
    driver, gpib_resource, transfer
):
    driver._instr = gpib_resource
    gpib_resource.timeout = 5000
    gpib_resource.read_termination = "\n"
    failure = timeout_error()
    gpib_resource.query_ascii_values.side_effect = failure
    gpib_resource.read_bytes.side_effect = failure

    def diagnostic(command):
        gpib_resource.clear.assert_called_once()
        assert gpib_resource.read_termination == "\n"
        return "16" if command == "*ESR?" else "0"

    gpib_resource.query.side_effect = diagnostic
    with pytest.raises(InstrumentError, match="cannot execute") as caught:
        if transfer == "ascii":
            driver._query_ascii_values("TRCA? 1,0,1")
        else:
            driver._read_buffer_bytes("TRCB? 1,0,1", 4)
    assert caught.value.__cause__ is failure
    assert gpib_resource.timeout == 5000


def test_fault_in_trace_prevents_requested_loop_resume(simulation):
    simulation.sample_rate = settings.SampleRate.Hz_1
    simulation.end_of_buffer_mode = settings.EndOfBufferMode.LOOP
    simulation.start()
    simulation.advance_time(1)
    simulation.inject_status("lia_status", settings.LiaStatusFlag.INPUT_OVERLOAD)
    with pytest.raises(InstrumentError, match="Input or amplifier overload"):
        simulation.get_ascii_buffer_data(1, 0, 1, resume=True)
    points = simulation.buffer_size
    simulation.advance_time(2)
    assert simulation.buffer_size == points


def test_simulated_queued_query_honors_timeout(simulation):
    simulation._raw_write("APHS")
    with simulation._io_timeout(0.01):
        with pytest.raises(pyvisa.errors.VisaIOError):
            simulation.idn
    assert simulation.idn  # Recovery waited for the queued command to complete.
