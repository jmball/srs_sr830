"""Configure a real SR830 and read coherent X/Y/R/phase values.

Requires --resource-name. Changes reference and measurement settings; connect a
suitable signal source before running. The instrument is not reset.
"""

import argparse

import pyvisa

from sr830 import (
    InputConfiguration,
    LowPassFilterSlope,
    MeasurementParameter,
    ReferenceSource,
    ReserveMode,
    Sensitivity,
    SR830,
    TimeConstant,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-name", required=True, help="VISA resource name")
    parser.add_argument(
        "--output-interface",
        type=int,
        choices=(0, 1),
        help="instrument-side interface for ambiguous adapters: 0=RS232, 1=GPIB",
    )
    parser.add_argument("--visa-backend", default="", help="VISA backend, such as @py")
    parser.add_argument(
        "--baud-rate",
        type=int,
        help="native serial baud rate; must match the instrument",
    )
    args = parser.parse_args()

    manager = pyvisa.ResourceManager(args.visa_backend)
    try:
        serial_kwargs: dict[str, int] = {}
        if args.baud_rate is not None:
            serial_kwargs["baud_rate"] = args.baud_rate
        with SR830() as instrument:
            instrument.connect(
                args.resource_name,
                resource_manager=manager,
                output_interface=args.output_interface,
                **serial_kwargs,
            )

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
    finally:
        # Disconnect the instrument before closing the application-owned manager.
        manager.close()


if __name__ == "__main__":
    main()
