"""Deterministic signal, acquisition, and status behavior without hardware."""

import math

import pytest

from sr830 import (
    Channel1Display,
    Channel1Ratio,
    DataTransferMode,
    EndOfBufferMode,
    ErrorFlag,
    InputConfiguration,
    LowPassFilterSlope,
    MeasurementParameter,
    OutputExpansion,
    OutputParameter,
    ReferenceSource,
    ReserveMode,
    SampleRate,
    Sensitivity,
    SerialPollFlag,
    StandardEventFlag,
    StatusRegister,
    TimeConstant,
    TriggerStartMode,
)
from virtual_sr830 import VirtualSR830


@pytest.fixture
def simulation():
    instrument = VirtualSR830(clock=lambda: 0.0)
    instrument.connect("GPIB0::8::INSTR")
    return instrument


def test_simulation_requires_connection_and_preserves_state_across_reconnect():
    instrument = VirtualSR830(clock=lambda: 0.0)
    for operation in (lambda: instrument.idn, instrument.reset, instrument.start):
        with pytest.raises(RuntimeError, match="not connected"):
            operation()
    instrument.connect("ASRL1::INSTR")
    instrument.reference_frequency = 2000
    instrument.disconnect()
    instrument.disconnect()
    with pytest.raises(RuntimeError, match="not connected"):
        instrument.measure(1)
    instrument.connect("ASRL1::INSTR")
    assert instrument.reference_frequency == 2000
    assert instrument.output_interface == 0


@pytest.mark.parametrize("slope", list(LowPassFilterSlope))
def test_cascaded_filter_step_response(simulation, slope):
    simulation.time_constant = TimeConstant.s_1
    simulation.lowpass_filter_slope = slope
    simulation.set_signal(0, settle=True)
    simulation.set_signal(1)
    simulation.advance_time(1)
    expected = 1 - math.exp(-1) * sum(
        1 / math.factorial(k) for k in range(int(slope) + 1)
    )
    assert simulation.measure(MeasurementParameter.X) == pytest.approx(expected)
    simulation.wait_for_settling(timeout=20)
    assert simulation.measure(1) == pytest.approx(1, abs=0.005)


def test_phase_and_coherent_snapshot(simulation):
    simulation.set_signal(0.003, 0.004, settle=True)
    x, y, r, phase = simulation.measure_multiple([1, 2, 3, 4])
    assert (x, y, r) == pytest.approx((0.003, 0.004, 0.005))
    assert phase == pytest.approx(math.degrees(math.atan2(0.004, 0.003)))
    simulation.reference_phase_shift = 90
    assert tuple(simulation.measure_multiple([1, 2])) == pytest.approx((0.004, -0.003))


def test_offsets_do_not_change_r_or_phase_and_expansion_does_not_scale_display(
    simulation,
):
    simulation.sensitivity = Sensitivity.x10m
    simulation.set_signal(0.003, 0.004, settle=True)
    simulation.set_output_offset_expand(OutputParameter.X, 20, OutputExpansion.x100)
    assert simulation.read_display(1) == pytest.approx(0.001)
    assert simulation.measure(3) == pytest.approx(0.005)
    simulation.set_aux_input(1, 2)
    simulation.set_display(1, Channel1Display.X, Channel1Ratio.AUX_IN_1)
    assert simulation.read_display(1) == pytest.approx(100)  # ratio clips at 100%
    simulation.set_output_offset_expand(OutputParameter.X, 20, OutputExpansion.x1)
    assert simulation.read_display(1) == pytest.approx(5)


def test_auxiliary_inputs_are_independent_of_outputs(simulation):
    simulation.set_aux_input(1, 2.5)
    simulation.set_aux_out(1, -1)
    assert simulation.get_aux_in(1) == 2.5
    assert simulation.get_aux_out(1) == -1
    simulation.set_display(1, Channel1Display.AUX_IN_1)
    assert simulation.read_display(1) == 2.5
    assert tuple(simulation.measure_multiple([5, 10])) == (2.5, 2.5)


def test_external_reference_lock_and_internal_frequency_are_separate(simulation):
    simulation.reference_frequency = 1234
    simulation.reference_source = ReferenceSource.EXTERNAL
    simulation.set_external_reference(42)
    assert simulation.reference_frequency == 42
    with pytest.raises(ValueError, match="internal reference"):
        simulation.reference_frequency = 200
    simulation.set_external_reference(42, locked=False)
    assert simulation.reference_frequency == 0
    simulation.reference_source = ReferenceSource.INTERNAL
    assert simulation.reference_frequency == 1234


def test_auto_settings_have_measurement_effects_and_busy_state(simulation):
    simulation.set_signal(0.003, 0.004, settle=True)
    simulation.auto_phase()
    assert not simulation.serial_poll() & SerialPollFlag.NO_COMMAND_IN_PROGRESS
    simulation.wait_until_ready()
    assert simulation.serial_poll() & SerialPollFlag.NO_COMMAND_IN_PROGRESS
    assert simulation.measure(2) == pytest.approx(0, abs=1e-12)
    simulation.auto_gain()
    assert simulation.sensitivity == Sensitivity.x5m
    simulation.auto_offset(1)
    assert simulation.read_display(1) == pytest.approx(0, abs=1e-12)
    simulation.reserve_mode = ReserveMode.HIGH_RESERVE
    simulation.auto_reserve()
    assert simulation.reserve_mode == ReserveMode.LOW_NOISE


def test_auto_gain_obeys_long_time_constant_constraint(simulation):
    simulation.time_constant = TimeConstant.s_3
    before = simulation.sensitivity
    simulation.auto_gain()
    assert simulation.sensitivity == before


def test_completion_and_settling_timeout(simulation):
    simulation.auto_phase()
    with pytest.raises(TimeoutError):
        simulation.wait_until_ready(timeout=0.01)
    simulation.wait_until_ready()
    simulation.time_constant = TimeConstant.s_1
    with pytest.raises(TimeoutError):
        simulation.wait_for_settling(timeout=1)


def test_save_and_recall_copy_complete_configuration(simulation):
    simulation.reference_frequency = 123
    simulation.set_aux_out(1, 0.5)
    simulation.set_front_output(1, 0)
    simulation.set_display(1, 1)
    simulation.set_output_offset_expand(1, 5, 1)
    simulation.save_setup(1)
    simulation.reset()
    simulation.recall_setup(1)
    assert simulation.reference_frequency == 123
    assert simulation.get_aux_out(1) == 0.5
    assert simulation.get_front_output(1) == 0
    assert simulation.get_display(1) == (1, 0)
    assert simulation.get_output_offset_expand(1) == (5, 1)
    simulation.set_aux_out(1, 1)
    simulation.recall_setup(1)
    assert simulation.get_aux_out(1) == 0.5
    with pytest.raises(ValueError, match="No setup saved"):
        simulation.recall_setup(2)
    assert (
        simulation.get_status_byte("standard_event") & StandardEventFlag.EXECUTION_ERROR
    )


def test_reset_preserves_interface_and_status_registers(simulation):
    simulation.output_interface = 0
    simulation.inject_status("error", ErrorFlag.RAM_ERROR)
    simulation.set_enable_register("error", ErrorFlag.RAM_ERROR)
    simulation.reset()
    assert simulation.output_interface == 0
    assert simulation.get_enable_register("error") == ErrorFlag.RAM_ERROR
    assert simulation.get_status_byte("error") == ErrorFlag.RAM_ERROR
    assert simulation.sensitivity == Sensitivity.x1
    assert simulation.time_constant == TimeConstant.ms_100
    assert simulation.sample_rate == SampleRate.Hz_1


def test_register_masks_bit_writes_and_clear_on_read(simulation):
    simulation.clear_status_registers()
    simulation.set_enable_register("error", 0)
    simulation.inject_status("error", ErrorFlag.RAM_ERROR | ErrorFlag.ROM_ERROR)
    assert not simulation.get_status_byte("serial_poll") & SerialPollFlag.ERROR
    simulation.set_enable_register("error", 1, decimal=False, bit=2)
    assert simulation.get_enable_register("error") == 4
    assert simulation.get_status_byte("serial_poll") & SerialPollFlag.ERROR
    assert simulation.get_status_byte("error", 2) == 1
    assert simulation.get_status_byte("error") == ErrorFlag.ROM_ERROR
    assert simulation.get_status_byte("error") == 0
    simulation.inject_status("standard_event", StandardEventFlag.EXECUTION_ERROR)
    simulation.clear_status_registers()
    assert simulation.get_status_byte("standard_event") == 0


def test_native_poll_acknowledges_srq(simulation):
    simulation.set_enable_register("serial_poll", SerialPollFlag.ERROR)
    simulation.inject_status("error", ErrorFlag.RAM_ERROR)
    assert simulation.serial_poll() & SerialPollFlag.SERVICE_REQUEST
    assert not simulation.serial_poll() & SerialPollFlag.SERVICE_REQUEST
    simulation.inject_status("error", ErrorFlag.ROM_ERROR)
    assert simulation.serial_poll() & SerialPollFlag.SERVICE_REQUEST


def test_acquisition_pause_resume_and_all_encodings(simulation):
    simulation.sample_rate = SampleRate.Hz_16
    simulation.set_signal(0.001, -0.002, settle=True)
    simulation.start()
    simulation.advance_time(0.25)
    assert simulation.buffer_size == 4
    simulation.pause()
    simulation.advance_time(5)
    assert simulation.buffer_size == 4
    for reader_name in (
        "get_ascii_buffer_data",
        "get_binary_buffer_data",
        "get_non_norm_buffer_data",
    ):
        reader = getattr(simulation, reader_name)
        assert reader(1, 0, 4) == pytest.approx((0.001,) * 4, rel=1e-4)
        assert reader(2, 0, 4) == pytest.approx((-0.002,) * 4, rel=1e-4)
    simulation.get_ascii_buffer_data(1, 0, 4, resume=True)
    simulation.advance_time(0.125)
    assert simulation.buffer_size == 6
    simulation.reset_data_buffers()
    assert simulation.buffer_size == 0


def test_trigger_start_does_not_store_first_trigger(simulation):
    simulation.sample_rate = SampleRate.TRIGGER
    simulation.trigger_start_mode = TriggerStartMode.START_SCAN
    simulation.trigger()
    assert simulation.buffer_size == 0
    simulation.trigger()
    simulation.trigger()
    assert simulation.buffer_size == 2
    simulation.advance_time(5)
    assert simulation.buffer_size == 2


@pytest.mark.parametrize("mode", list(EndOfBufferMode))
def test_physical_buffer_capacity_and_loop_order(simulation, mode):
    simulation.sample_rate = SampleRate.Hz_512
    simulation.end_of_buffer_mode = mode
    simulation.start()
    simulation.advance_time(16384 / 512)
    assert simulation.buffer_size == 16383
    simulation.set_signal(0.002, settle=True)
    simulation.advance_time(1 / 512)
    last = simulation.get_ascii_buffer_data(1, 16382, 1)[0]
    assert last == pytest.approx(0.002 if mode == EndOfBufferMode.LOOP else 0.001)
    assert bool(simulation.serial_poll() & SerialPollFlag.NO_SCAN_IN_PROGRESS) == (
        mode == EndOfBufferMode.ONE_SHOT
    )


@pytest.mark.parametrize("mode", [DataTransferMode.DOS, DataTransferMode.WINDOWS])
def test_fast_stream_uses_counts_and_delayed_start(simulation, mode):
    simulation.sensitivity = Sensitivity.x10m
    simulation.set_signal(0.005, -0.0025, settle=True)
    simulation.sample_rate = SampleRate.Hz_16
    simulation.data_transfer_mode = mode
    simulation.start()
    simulation.advance_time(0.4)
    assert not simulation._simulation.fast
    assert simulation.read_fast_data(2, timeout=0.5) == ((15000, -7500),) * 2
    with pytest.raises(RuntimeError, match="Stop fast"):
        simulation.idn
    simulation.pause()
    assert simulation.buffer_size == 2
    assert simulation.data_transfer_mode == mode
    assert simulation._simulation.fast == simulation._simulation.fast.__class__()


def test_fast_counts_include_expansion_and_current_units(simulation):
    simulation.input_configuration = InputConfiguration.CURRENT_1_MOHM
    simulation.sensitivity = Sensitivity.x10m  # 10 nA full scale
    simulation.set_signal(2e-9, 0, settle=True)
    simulation.set_output_offset_expand(1, 10, OutputExpansion.x10)
    simulation.sample_rate = SampleRate.Hz_16
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    assert simulation.read_fast_data(1, timeout=1) == ((30000, 0),)


def test_fast_timeout_stops_scan_and_keeps_text_usable(simulation):
    simulation.sample_rate = SampleRate.TRIGGER
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    with pytest.raises(TimeoutError):
        simulation.read_fast_data(1, timeout=0.1)
    assert simulation.idn
    assert not simulation._simulation.running


def test_fast2_queue_overflow_latches_error_and_disables_transfer(simulation):
    simulation.sample_rate = SampleRate.Hz_512
    simulation.data_transfer_mode = DataTransferMode.WINDOWS
    simulation.start()
    simulation.advance_time(1)
    simulation.pause()
    assert simulation.data_transfer_mode == DataTransferMode.OFF
    assert simulation.get_status_byte(StatusRegister.ERROR) & ErrorFlag.GPIB_ERROR


def test_signal_callback_drives_acquisition_at_sample_times():
    simulation = VirtualSR830(clock=lambda: 0.0, signal=lambda t: complex(t, -t))
    simulation.connect("GPIB0::8::INSTR")
    simulation.sample_rate = SampleRate.Hz_1
    simulation.time_constant = TimeConstant.us_10
    simulation.start()
    simulation.advance_time(3)
    assert simulation.get_ascii_buffer_data(1, 0, 3) == (1.0, 2.0, 3.0)
    assert simulation.get_ascii_buffer_data(2, 0, 3) == (-1.0, -2.0, -3.0)


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: s.advance_time(-1),
        lambda s: s.set_signal(float("nan")),
        lambda s: s.set_aux_input(0, 0),
        lambda s: s.set_aux_input(1, 11),
        lambda s: s.set_external_reference(0),
        lambda s: s.inject_status("serial_poll", 1),
    ],
)
def test_simulation_controls_validate_inputs(simulation, operation):
    with pytest.raises(ValueError):
        operation(simulation)


def test_disconnect_clears_connection_even_if_signal_callback_fails():
    source = [complex(0.001)]
    simulation = VirtualSR830(clock=lambda: 0.0, signal=lambda _: source[0])
    simulation.connect("GPIB0::8::INSTR")
    source[0] = complex(float("nan"))
    with pytest.raises(ValueError, match="finite components"):
        simulation.disconnect()
    assert not simulation._connected
    simulation.disconnect()
    with pytest.raises(RuntimeError, match="not connected"):
        simulation.idn
