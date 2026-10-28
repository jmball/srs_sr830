"""Deterministic signal, acquisition, and status behavior without hardware."""

import math

import pytest

from sr830 import (
    Channel1Display,
    Channel1Ratio,
    Channel2Display,
    Channel2Ratio,
    DataTransferMode,
    EndOfBufferMode,
    ErrorFlag,
    InputConfiguration,
    InstrumentError,
    LiaStatusFlag,
    LowPassFilterSlope,
    MeasurementParameter,
    OutputExpansion,
    OutputInterface,
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

pytestmark = pytest.mark.usefixtures("simulation_clock")


def test_simulation_requires_connection_and_preserves_state_across_reconnect():
    instrument = VirtualSR830()
    for operation in (lambda: instrument.idn, instrument.reset, instrument.start):
        with pytest.raises(RuntimeError, match="not connected"):
            operation()
    instrument.connect(output_interface=OutputInterface.RS232)
    instrument.reference_frequency = 2000
    instrument.disconnect()
    instrument.disconnect()
    with pytest.raises(RuntimeError, match="not connected"):
        instrument.measure(1)
    instrument.connect(output_interface=OutputInterface.RS232)
    assert instrument.reference_frequency == 2000
    assert instrument.output_interface == 0


@pytest.mark.parametrize("slope", list(LowPassFilterSlope))
def test_cascaded_filter_step_response(simulation, slope, simulation_clock):
    simulation.time_constant = TimeConstant.s_1
    simulation.lowpass_filter_slope = slope
    simulation.amplitude = 0
    simulation.phase = 0
    simulation.wait_for_settling(time_constants=101)
    simulation.amplitude = 1
    simulation.phase = 0
    simulation_clock.advance(1)
    expected = 1 - math.exp(-1) * sum(
        1 / math.factorial(k) for k in range(int(slope) + 1)
    )
    assert simulation.measure(MeasurementParameter.X) == pytest.approx(expected)
    simulation.wait_for_settling()
    assert simulation.measure(1) == pytest.approx(1, abs=0.005)


def test_phase_and_coherent_snapshot(simulation):
    simulation.amplitude = math.hypot(0.003, 0.004)
    simulation.phase = math.degrees(math.atan2(0.004, 0.003))
    simulation.wait_for_settling(time_constants=101)
    x, y, r, phase = simulation.measure_multiple([1, 2, 3, 4])
    assert (x, y, r) == pytest.approx((0.003, 0.004, 0.005))
    assert phase == pytest.approx(math.degrees(math.atan2(0.004, 0.003)))
    simulation.reference_phase_shift = 90
    assert tuple(simulation.measure_multiple([1, 2])) == pytest.approx((0.004, -0.003))


def test_offsets_do_not_change_r_or_phase_and_expansion_does_not_scale_display(
    simulation,
):
    simulation.sensitivity = Sensitivity.x10m
    simulation.amplitude = math.hypot(0.003, 0.004)
    simulation.phase = math.degrees(math.atan2(0.004, 0.003))
    simulation.wait_for_settling(time_constants=101)
    simulation.set_output_offset_expand(OutputParameter.X, 20, OutputExpansion.x100)
    assert simulation.read_display(1) == pytest.approx(0.001)
    assert simulation.measure(3) == pytest.approx(0.005)
    assert simulation.measure(4) == pytest.approx(
        math.degrees(math.atan2(0.004, 0.003))
    )
    simulation.set_aux_input(1, 2)
    simulation.set_display(1, Channel1Display.X, Channel1Ratio.AUX_IN_1)
    assert simulation.read_display(1) == pytest.approx(100)  # ratio clips at 100%
    simulation.set_output_offset_expand(OutputParameter.X, 20, OutputExpansion.x1)
    assert simulation.read_display(1) == pytest.approx(5)


@pytest.mark.parametrize(
    "channel, display, ratio, expected",
    [
        (1, Channel1Display.R, Channel1Ratio.NONE, 0.005),
        (2, Channel2Display.PHASE, Channel2Ratio.NONE, 53.1301023542),
        (1, Channel1Display.X_NOISE, Channel1Ratio.NONE, 0.0),
        (2, Channel2Display.Y_NOISE, Channel2Ratio.NONE, 0.0),
    ],
    ids=["ch1-r", "ch2-phase", "ch1-ideal-noise", "ch2-ideal-noise"],
)
def test_display_quantities(simulation, channel, display, ratio, expected):
    simulation.amplitude = math.hypot(0.003, 0.004)
    simulation.phase = math.degrees(math.atan2(0.004, 0.003))
    simulation.wait_for_settling(time_constants=101)
    simulation.set_display(channel, display, ratio)
    assert simulation.read_display(channel) == pytest.approx(expected)


@pytest.mark.parametrize(
    "channel, display, ratio, aux_channel, expected",
    [
        (1, Channel1Display.X, Channel1Ratio.AUX_IN_1, 1, 0.15),
        (1, Channel1Display.X, Channel1Ratio.AUX_IN_2, 2, 0.15),
        (2, Channel2Display.Y, Channel2Ratio.AUX_IN_3, 3, 0.2),
        (2, Channel2Display.Y, Channel2Ratio.AUX_IN_4, 4, 0.2),
    ],
    ids=["ch1-aux1", "ch1-aux2", "ch2-aux3", "ch2-aux4"],
)
def test_display_ratios_use_channel_aux_inputs(
    simulation, channel, display, ratio, aux_channel, expected
):
    simulation.amplitude = math.hypot(0.003, 0.004)
    simulation.phase = math.degrees(math.atan2(0.004, 0.003))
    simulation.wait_for_settling(time_constants=101)
    simulation.set_aux_input(aux_channel, 2)
    simulation.set_display(channel, display, ratio)
    assert simulation.read_display(channel) == pytest.approx(expected)


def test_zero_display_ratio_denominator_sets_overload(simulation):
    simulation.amplitude = 0.003
    simulation.phase = 0
    simulation.wait_for_settling(time_constants=101)
    simulation.set_display(1, Channel1Display.X, Channel1Ratio.AUX_IN_1)
    with pytest.raises(InstrumentError, match="Output overload"):
        simulation.read_display(1)


def test_snap_includes_reference_frequency(simulation):
    simulation.reference_frequency = 1234.5
    values = simulation.measure_multiple(
        [MeasurementParameter.REFERENCE_FREQUENCY, MeasurementParameter.X]
    )
    assert tuple(values) == (1234.5, 0.001)


def test_harmonic_is_clamped_to_detection_frequency_limit(simulation):
    simulation.reference_frequency = 1000
    simulation.harmonic = 200
    assert simulation.harmonic == 102


def test_switching_to_current_sensitivity_clamps_input_configuration(simulation):
    simulation.input_configuration = InputConfiguration.CURRENT_100_MOHM
    simulation.sensitivity = Sensitivity.x20m
    assert simulation.input_configuration == InputConfiguration.CURRENT_1_MOHM


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
    with pytest.raises(InstrumentError, match="cannot execute"):
        simulation.reference_frequency = 200
    simulation.set_external_reference(42, locked=False)
    assert simulation.reference_frequency == 0
    simulation.reference_source = ReferenceSource.INTERNAL
    assert simulation.reference_frequency == 1234


def test_auto_settings_take_effect_without_elapsed_time(simulation, simulation_clock):
    simulation.amplitude = math.hypot(0.003, 0.004)
    simulation.phase = math.degrees(math.atan2(0.004, 0.003))
    simulation.wait_for_settling(time_constants=101)
    started = simulation_clock()
    simulation.auto_phase()
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

    assert simulation_clock() == started


def test_auto_gain_obeys_long_time_constant_constraint(simulation):
    simulation.time_constant = TimeConstant.s_3
    before = simulation.sensitivity
    simulation.auto_gain()
    assert simulation.sensitivity == before


def test_settling_default_uses_current_instrument_configuration(
    simulation, simulation_clock
):
    simulation.time_constant = TimeConstant.s_1
    simulation.lowpass_filter_slope = LowPassFilterSlope.dB_12
    started = simulation_clock()
    simulation.wait_for_settling()
    assert simulation_clock() - started == 7


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
    with pytest.raises(InstrumentError, match="cannot execute"):
        simulation.recall_setup(2)


def test_reset_preserves_interface_and_status_registers(simulation):
    simulation.output_interface = 0
    simulation.set_enable_register("error", ErrorFlag.RAM_ERROR)
    simulation.inject_status("error", ErrorFlag.RAM_ERROR)
    # Inspect the protocol operation before automatic checks consume the latch.
    simulation._raw_write("*RST")
    assert simulation.get_status_byte("error") == ErrorFlag.RAM_ERROR
    assert simulation.output_interface == 0
    assert simulation.get_enable_register("error") == ErrorFlag.RAM_ERROR
    assert simulation.sensitivity == Sensitivity.x1
    assert simulation.time_constant == TimeConstant.ms_100
    assert simulation.sample_rate == SampleRate.Hz_1


def test_register_masks_bit_writes_and_clear_on_read(simulation):
    simulation.clear_status_registers()
    simulation.set_enable_register("error", 0)
    simulation.inject_status("error", ErrorFlag.RAM_ERROR | ErrorFlag.ROM_ERROR)
    assert not simulation.get_status_byte("serial_poll") & SerialPollFlag.ERROR
    # Raw I/O deliberately preserves the fault latches for this register test.
    simulation._raw_write("ERRE 2,1")
    assert simulation._raw_query("ERRE?") == "4"
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


def test_acquisition_pause_resume_and_all_encodings(simulation, simulation_clock):
    simulation.sample_rate = SampleRate.Hz_16
    simulation.amplitude = math.hypot(0.001, -0.002)
    simulation.phase = math.degrees(math.atan2(-0.002, 0.001))
    simulation.wait_for_settling(time_constants=101)
    simulation.start()
    simulation_clock.advance(0.25)
    assert simulation.buffer_size == 4
    simulation.pause()
    simulation_clock.advance(5)
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
    simulation_clock.advance(0.125)
    assert simulation.buffer_size == 6
    simulation.reset_data_buffers()
    assert simulation.buffer_size == 0


def test_trigger_start_does_not_store_first_trigger(simulation, simulation_clock):
    simulation.sample_rate = SampleRate.TRIGGER
    simulation.trigger_start_mode = TriggerStartMode.START_SCAN
    simulation.trigger()
    assert simulation.buffer_size == 0
    simulation.trigger()
    simulation.trigger()
    assert simulation.buffer_size == 2
    simulation_clock.advance(5)
    assert simulation.buffer_size == 2


@pytest.mark.parametrize("mode", list(EndOfBufferMode))
def test_physical_buffer_capacity_and_loop_order(simulation, mode, simulation_clock):
    simulation.sample_rate = SampleRate.Hz_512
    simulation.end_of_buffer_mode = mode
    simulation.start()
    simulation_clock.advance(16384 / 512)
    assert simulation.buffer_size == 16383
    simulation.amplitude = 0.002
    simulation.phase = 0
    simulation.wait_for_settling(time_constants=101)
    simulation_clock.advance(1 / 512)
    last = simulation.get_ascii_buffer_data(1, 16382, 1)[0]
    assert last == pytest.approx(0.002 if mode == EndOfBufferMode.LOOP else 0.001)
    assert bool(simulation.serial_poll() & SerialPollFlag.NO_SCAN_IN_PROGRESS) == (
        mode == EndOfBufferMode.ONE_SHOT
    )


@pytest.mark.parametrize("mode", [DataTransferMode.DOS, DataTransferMode.WINDOWS])
def test_fast_stream_uses_counts_and_delayed_start(simulation, mode, simulation_clock):
    simulation.sensitivity = Sensitivity.x10m
    simulation.amplitude = math.hypot(0.005, -0.0025)
    simulation.phase = math.degrees(math.atan2(-0.0025, 0.005))
    simulation.wait_for_settling(time_constants=101)
    simulation.sample_rate = SampleRate.Hz_16
    simulation.data_transfer_mode = mode
    simulation.start()
    simulation_clock.advance(0.4)
    assert not simulation.serial_poll() & SerialPollFlag.MESSAGE_AVAILABLE
    assert simulation.read_fast_data(2, timeout=0.5) == ((15000, -7500),) * 2
    with pytest.raises(RuntimeError, match="Stop fast"):
        simulation.idn
    simulation.pause()
    assert simulation.buffer_size == 2
    assert simulation.data_transfer_mode == mode


def test_fast_data_sets_message_available_status(simulation, simulation_clock):
    simulation.sample_rate = SampleRate.Hz_16
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    assert not simulation.serial_poll() & SerialPollFlag.MESSAGE_AVAILABLE
    simulation_clock.advance(0.625)
    assert simulation.serial_poll() & SerialPollFlag.MESSAGE_AVAILABLE
    simulation.pause()


def test_non_normalized_buffer_handles_mantissa_rounding_boundary(
    simulation, simulation_clock
):
    sample = math.nextafter(0.5, 0.0)
    simulation.amplitude = sample
    simulation.phase = 0
    simulation.wait_for_settling(time_constants=101)
    simulation.sample_rate = SampleRate.Hz_1
    simulation.start()
    simulation_clock.advance(1)
    assert simulation.get_non_norm_buffer_data(1, 0, 1) == pytest.approx((sample,))


def test_fast_counts_include_expansion_and_current_units(simulation):
    simulation.input_configuration = InputConfiguration.CURRENT_1_MOHM
    simulation.sensitivity = Sensitivity.x10m  # 10 nA full scale
    simulation.amplitude = 2e-9
    simulation.phase = 0
    simulation.wait_for_settling(time_constants=101)
    simulation.set_output_offset_expand(1, 10, OutputExpansion.x10)
    simulation.sample_rate = SampleRate.Hz_16
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    assert simulation.read_fast_data(1, timeout=1) == ((30000, 0),)


def test_fast_timeout_stops_scan_and_keeps_text_usable(simulation, simulation_clock):
    simulation.sample_rate = SampleRate.Hz_16
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    with pytest.raises(TimeoutError):
        simulation.read_fast_data(1, timeout=0.1)
    assert simulation.idn
    points = simulation.buffer_size
    simulation_clock.advance(1)
    assert simulation.buffer_size == points


def test_fast2_queue_overflow_latches_error_and_disables_transfer(
    simulation, simulation_clock
):
    simulation.sample_rate = SampleRate.Hz_512
    simulation.data_transfer_mode = DataTransferMode.WINDOWS
    simulation.start()
    simulation_clock.advance(1)
    with pytest.raises(InstrumentError, match="fast data transfer mode aborted"):
        simulation.pause()
    assert simulation.data_transfer_mode == DataTransferMode.OFF


def test_input_properties_drive_subsequent_acquisition_samples(
    simulation, simulation_clock
):
    simulation.time_constant = TimeConstant.us_10
    simulation.sample_rate = SampleRate.Hz_1
    simulation.phase = 0
    simulation.start()
    for amplitude in (0.1, 0.2, 0.3):
        simulation.amplitude = amplitude
        simulation_clock.advance(1)
    assert simulation.get_ascii_buffer_data(1, 0, 3) == pytest.approx((0.1, 0.2, 0.3))
    assert simulation.get_ascii_buffer_data(2, 0, 3) == (0, 0, 0)


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: setattr(s, "amplitude", float("nan")),
        lambda s: setattr(s, "amplitude", -1),
        lambda s: setattr(s, "phase", float("inf")),
        lambda s: s.set_aux_input(0, 0),
        lambda s: s.set_aux_input(1, 11),
        lambda s: s.set_external_reference(0),
        lambda s: s.inject_status("serial_poll", 1),
    ],
)
def test_simulation_controls_validate_inputs(simulation, operation):
    with pytest.raises(ValueError):
        operation(simulation)


def test_disconnect_clears_connection_even_if_model_update_fails(
    simulation, monkeypatch
):
    def fail_update():
        raise OSError("model update failed")

    monkeypatch.setattr(simulation, "_update_state", fail_update)
    with pytest.raises(OSError, match="model update failed"):
        simulation.disconnect()
    assert not simulation._connected
    simulation.disconnect()
    with pytest.raises(RuntimeError, match="not connected"):
        simulation.idn


@pytest.mark.parametrize(
    "channel,display,ratio,expected",
    [
        pytest.param(
            1, Channel1Display.R, Channel1Ratio.AUX_IN_1, 2.5, id="expanded-r"
        ),
        pytest.param(
            2,
            Channel2Display.PHASE,
            Channel2Ratio.AUX_IN_3,
            math.degrees(math.atan2(0.004, 0.003)) / 180 * 50,
            id="phase",
        ),
        pytest.param(
            1, Channel1Display.AUX_IN_2, Channel1Ratio.AUX_IN_1, 20, id="aux-voltage"
        ),
        pytest.param(
            1, Channel1Display.X_NOISE, Channel1Ratio.AUX_IN_1, 0, id="ideal-noise"
        ),
    ],
)
def test_ratio_scales_match_display_units(
    simulation, channel, display, ratio, expected
):
    simulation.amplitude = math.hypot(0.003, 0.004)
    simulation.phase = math.degrees(math.atan2(0.004, 0.003))
    simulation.wait_for_settling(time_constants=101)
    simulation.set_aux_input(1, 2)
    simulation.set_aux_input(2, 4)
    simulation.set_aux_input(3, 2)
    simulation.set_output_offset_expand(OutputParameter.R, 0, OutputExpansion.x10)
    simulation.set_display(channel, display, ratio)
    assert simulation.read_display(channel) == pytest.approx(expected)


def test_harmonic_is_preserved_with_an_unlocked_reference(simulation):
    simulation.reference_source = ReferenceSource.EXTERNAL
    simulation.set_external_reference(1000, locked=False)
    simulation.harmonic = 200
    assert simulation.harmonic == 200


def test_repeated_start_does_not_reset_sample_timing(simulation, simulation_clock):
    simulation.sample_rate = SampleRate.Hz_1
    simulation.start()
    simulation_clock.advance(0.5)
    simulation.start()
    simulation_clock.advance(0.5)
    assert simulation.buffer_size == 1


def test_trigger_without_start_mode_latches_event_without_starting_scan(simulation):
    simulation.trigger()
    assert simulation.buffer_size == 0
    assert simulation.serial_poll() & SerialPollFlag.NO_SCAN_IN_PROGRESS
    assert simulation.get_status_byte(StatusRegister.LIA_STATUS) & LiaStatusFlag.TRIGGER


def test_virtual_connect_ignores_resource_name_and_manager(manager):
    simulation = VirtualSR830()
    simulation.connect("not a VISA resource name", resource_manager=manager)
    assert simulation.output_interface == OutputInterface.GPIB
    manager.resource_info.assert_not_called()
    manager.open_resource.assert_not_called()
    simulation.disconnect()
    manager.close.assert_not_called()


def test_virtual_stream_rejects_interface_change(simulation):
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    with pytest.raises(RuntimeError, match="Stop fast transfer"):
        simulation.output_interface = 0
    simulation.pause()


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        pytest.param(
            "set_external_reference", (1000,), {"locked": 1}, id="locked-not-bool"
        ),
    ],
)
def test_simulation_boolean_options_are_strict(simulation, method, args, kwargs):
    with pytest.raises(ValueError, match="must be a bool"):
        getattr(simulation, method)(*args, **kwargs)


def test_constructor_input_amplitude_and_phase_and_later_changes(simulation_clock):
    with VirtualSR830(amplitude=0.01, phase=30) as instrument:
        instrument.connect()
        assert instrument.amplitude == 0.01
        assert instrument.phase == 30
        assert tuple(instrument.measure_multiple([1, 2, 3, 4])) == pytest.approx(
            (0.01 * math.sqrt(3) / 2, 0.005, 0.01, 30)
        )
        instrument.amplitude = 0.02
        instrument.phase = 90
        # Updating the source does not bypass the low-pass filters.
        assert instrument.measure(1) == pytest.approx(0.01 * math.sqrt(3) / 2)
        instrument.wait_for_settling(time_constants=101)
        assert tuple(instrument.measure_multiple([1, 2])) == pytest.approx((0, 0.02))
        assert instrument.amplitude == 0.02
        assert instrument.phase == 90


@pytest.mark.parametrize(
    "kwargs", [{"amplitude": -1}, {"amplitude": float("nan")}, {"phase": float("inf")}]
)
def test_constructor_validates_input(kwargs):
    with pytest.raises(ValueError):
        VirtualSR830(**kwargs)


def test_waits_use_elapsed_time_and_selected_filter_settings(
    simulation, simulation_clock
):
    simulation.time_constant = TimeConstant.ms_100
    simulation.lowpass_filter_slope = LowPassFilterSlope.dB_12
    simulation.amplitude = 0.1
    started = simulation_clock()
    simulation.wait_for_settling(time_constants=3)
    assert simulation_clock() - started == pytest.approx(0.3)
    expected = 0.001 + 0.099 * (1 - 4 * math.exp(-3))
    assert simulation.measure(1) == pytest.approx(expected)


def test_triggered_fast_read_waits_for_timeout_and_restores_io_budget(
    simulation, simulation_clock
):
    simulation.sample_rate = SampleRate.TRIGGER
    simulation.data_transfer_mode = DataTransferMode.DOS
    simulation.start()
    previous = simulation._virtual_timeout
    started = simulation_clock()
    with pytest.raises(TimeoutError):
        simulation.read_fast_data(1, timeout=0.25)
    assert simulation_clock() - started == pytest.approx(0.25)
    assert simulation._virtual_timeout == previous
    assert simulation.idn


def test_constructor_external_frequency_and_auxiliary_inputs():
    inputs = [0.1, -0.2, 3.0, 4.0]
    with VirtualSR830(external_frequency=137, aux_inputs=inputs) as instrument:
        inputs[0] = 9.0  # The caller's mutable sequence is not retained.
        instrument.connect()
        assert instrument.reference_source == ReferenceSource.INTERNAL
        assert instrument.reference_frequency == 1000
        instrument.reference_source = ReferenceSource.EXTERNAL
        assert instrument.reference_frequency == 137
        assert tuple(instrument.get_aux_in(channel) for channel in range(1, 5)) == (
            0.1,
            -0.2,
            3.0,
            4.0,
        )
        assert instrument.get_aux_out(1) == 0
        instrument.reset()
        instrument.reference_source = ReferenceSource.EXTERNAL
        assert instrument.reference_frequency == 137
        assert instrument.get_aux_in(1) == 0.1
        instrument.set_external_reference(42)
        instrument.set_aux_input(1, 0.5)
        assert instrument.reference_frequency == 42
        assert instrument.get_aux_in(1) == 0.5


def test_default_constructor_conditions_are_independent_between_instances():
    with VirtualSR830() as first, VirtualSR830() as second:
        first.set_aux_input(1, 1)
        second.connect()
        second.reference_source = ReferenceSource.EXTERNAL
        assert second.reference_frequency == 1000
        assert tuple(second.get_aux_in(channel) for channel in range(1, 5)) == (
            0,
            0,
            0,
            0,
        )


def test_constructor_can_start_with_unlocked_external_reference():
    with VirtualSR830(external_frequency=137, external_locked=False) as instrument:
        instrument.connect()
        instrument.reference_source = ReferenceSource.EXTERNAL
        assert instrument.reference_frequency == 0
        with pytest.raises(InstrumentError, match="Reference unlock"):
            instrument.check_measurement_status()
        instrument.set_external_reference(137, locked=True)
        assert instrument.reference_frequency == 137


@pytest.mark.parametrize(
    "kwargs",
    [
        {"external_frequency": 0},
        {"external_locked": 1},
        {"aux_inputs": (0, 0, 0)},
        {"aux_inputs": (0, 0, float("nan"), 0)},
    ],
)
def test_constructor_validates_external_conditions(kwargs):
    with pytest.raises(ValueError):
        VirtualSR830(**kwargs)
