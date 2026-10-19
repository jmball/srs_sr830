"""Configure and measure a virtual SR830 without opening any hardware.

The simulator accepts demodulated RMS voltage components as its input signal.
Settling advances simulation time instead of sleeping.
"""

from virtual_sr830 import (
    InputConfiguration,
    LowPassFilterSlope,
    MeasurementParameter,
    ReferenceSource,
    ReserveMode,
    Sensitivity,
    VirtualSR830,
    TimeConstant,
)


def main() -> None:
    with VirtualSR830() as instrument:
        # The resource name selects the simulated interface; no VISA resource opens.
        instrument.connect("GPIB0::8::INSTR")
        instrument.set_signal(0.003, 0.004)  # X/Y components in V RMS.

        instrument.reference_source = ReferenceSource.INTERNAL
        instrument.harmonic = 1
        instrument.reference_frequency = 137.0
        instrument.input_configuration = InputConfiguration.A
        instrument.sensitivity = Sensitivity.x10m
        instrument.reserve_mode = ReserveMode.NORMAL
        instrument.lowpass_filter_slope = LowPassFilterSlope.dB_12
        instrument.time_constant = TimeConstant.ms_100

        instrument.wait_for_settling(timeout=5.0, time_constants=10.0)
        x, y, magnitude, phase = instrument.measure_multiple(
            [
                MeasurementParameter.X,
                MeasurementParameter.Y,
                MeasurementParameter.R,
                MeasurementParameter.PHASE,
            ]
        )
        print(f"X: {x:.6g} V RMS")
        print(f"Y: {y:.6g} V RMS")
        print(f"R: {magnitude:.6g} V RMS")
        print(f"Phase: {phase:.3f} degrees")


if __name__ == "__main__":
    main()
