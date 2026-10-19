"""Configure and measure a virtual SR830 without opening any hardware.

The simulator accepts demodulated RMS voltage components as its input signal.
Settling advances simulation time instead of sleeping.
"""

from sr830 import settings
from virtual_sr830 import VirtualSR830


def main() -> None:
    with VirtualSR830() as instrument:
        # The resource name selects the simulated interface; no VISA resource opens.
        instrument.connect(
            "GPIB0::8::INSTR", output_interface=settings.OutputInterface.GPIB
        )
        instrument.set_signal(0.003, 0.004)  # X/Y components in V RMS.

        # Reference oscillator and sine output.
        instrument.reference_source = settings.ReferenceSource.INTERNAL
        instrument.reference_trigger = settings.ReferenceTrigger.ZERO_CROSSING
        instrument.reference_phase_shift = 0.0
        instrument.harmonic = 1
        instrument.reference_frequency = 137.0
        instrument.sine_amplitude = 0.1

        # Input path and detection filters; configure slope and reserve before time constant.
        instrument.input_configuration = settings.InputConfiguration.A
        instrument.input_shield_grounding = settings.InputShieldGrounding.FLOAT
        instrument.input_coupling = settings.InputCoupling.AC
        instrument.line_notch_filter_status = settings.LineNotchFilter.OFF
        instrument.sensitivity = settings.Sensitivity.x10m
        instrument.reserve_mode = settings.ReserveMode.NORMAL
        instrument.lowpass_filter_slope = settings.LowPassFilterSlope.dB_12
        instrument.time_constant = settings.TimeConstant.ms_100
        instrument.sync_filter_status = settings.SynchronousFilter.OFF

        # Connection and front-panel controls.
        instrument.local_mode = settings.LocalMode.REMOTE
        instrument.gpib_override_remote = settings.GpibOverrideRemote.DISABLED
        instrument.key_click_state = settings.SwitchState.OFF
        instrument.alarm_status = settings.SwitchState.OFF
        instrument.power_on_status_clear_bit = settings.SwitchState.ON

        # Storage configuration; FAST stays off for ordinary measurements.
        instrument.sample_rate = settings.SampleRate.Hz_512
        instrument.end_of_buffer_mode = settings.EndOfBufferMode.ONE_SHOT
        instrument.trigger_start_mode = settings.TriggerStartMode.OFF
        instrument.data_transfer_mode = settings.DataTransferMode.OFF

        # Display/ratio selectors and front-panel output sources.
        instrument.set_display(
            settings.Channel.CH1,
            settings.Channel1Display.R,
            settings.Channel1Ratio.NONE,
        )
        instrument.set_display(
            settings.Channel.CH2,
            settings.Channel2Display.PHASE,
            settings.Channel2Ratio.NONE,
        )
        for channel in (settings.Channel.CH1, settings.Channel.CH2):
            instrument.set_front_output(
                channel, settings.FrontPanelOutputSource.DISPLAY
            )
        for parameter in (
            settings.OutputParameter.X,
            settings.OutputParameter.Y,
            settings.OutputParameter.R,
        ):
            instrument.set_output_offset_expand(
                parameter, 0.0, settings.OutputExpansion.x1
            )
        for auxiliary in settings.AuxiliaryChannel:
            instrument.set_aux_out(auxiliary, 0.0)

        # Enable selected status events with a register-specific mask.
        instrument.set_enable_register(
            settings.StatusRegister.STANDARD_EVENT,
            settings.StandardEventFlag.COMMAND_ERROR
            | settings.StandardEventFlag.EXECUTION_ERROR,
        )
        instrument.set_enable_register(
            settings.StatusRegister.SERIAL_POLL,
            settings.SerialPollFlag.ERROR
            | settings.SerialPollFlag.LIA_STATUS
            | settings.SerialPollFlag.STANDARD_EVENT,
        )
        instrument.set_enable_register(
            settings.StatusRegister.ERROR,
            settings.ErrorFlag.RAM_ERROR | settings.ErrorFlag.ROM_ERROR,
        )
        instrument.set_enable_register(
            settings.StatusRegister.LIA_STATUS,
            settings.LiaStatusFlag.INPUT_OVERLOAD
            | settings.LiaStatusFlag.REFERENCE_UNLOCK,
        )

        instrument.wait_for_settling(timeout=5.0, time_constants=10.0)
        x, y, magnitude, phase = instrument.measure_multiple(
            [
                settings.MeasurementParameter.X,
                settings.MeasurementParameter.Y,
                settings.MeasurementParameter.R,
                settings.MeasurementParameter.PHASE,
            ]
        )
        print(f"X: {x:.6g} V RMS")
        print(f"Y: {y:.6g} V RMS")
        print(f"R: {magnitude:.6g} V RMS")
        print(f"Phase: {phase:.3f} degrees")


if __name__ == "__main__":
    main()
