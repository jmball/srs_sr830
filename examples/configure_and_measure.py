"""Configure a real SR830 and read coherent X/Y/R/phase values.

Requires --resource-name. Changes instrument settings; connect a suitable
signal source before running. The instrument is not reset.
"""

import argparse

import pyvisa

from sr830 import SR830, settings


def parse_args() -> argparse.Namespace:
    """Parse VISA connection options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-name", required=True, help="VISA resource name")
    parser.add_argument(
        "--output-interface",
        type=int,
        choices=(0, 1),
        help="instrument-side interface for ambiguous adapters: 0=RS232, 1=GPIB",
    )
    parser.add_argument(
        "--visa-backend", default="@py", help="VISA backend (default: @py)"
    )
    parser.add_argument(
        "--baud-rate",
        type=int,
        help="native serial baud rate; must match the instrument",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    serial_kwargs: dict[str, int] = {}
    if args.baud_rate is not None:
        serial_kwargs["baud_rate"] = args.baud_rate

    manager = pyvisa.ResourceManager(args.visa_backend)
    with SR830() as instrument:
        # Select the response interface when connecting; do not switch transports later.
        instrument.connect(
            args.resource_name,
            resource_manager=manager,
            output_interface=(
                settings.OutputInterface(args.output_interface)
                if args.output_interface is not None
                else None
            ),
            **serial_kwargs,
        )

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
