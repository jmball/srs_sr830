"""Configure an SR830 and print a coherent X/Y/R/phase measurement.

The default virtual instrument is safe to run without hardware. Supplying a
VISA resource selects a real SR830 and changes its measurement settings.
"""

from __future__ import annotations

import argparse
from typing import Sequence

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
from virtual_sr830 import VirtualSR830


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resource-name",
        help="VISA resource name; omit to use VirtualSR830 without hardware",
    )
    parser.add_argument(
        "--output-interface",
        type=int,
        choices=(0, 1),
        help="instrument response interface for ambiguous adapters: 0=RS232, 1=GPIB",
    )
    parser.add_argument(
        "--visa-backend",
        help="optional PyVISA backend for real hardware, such as @py",
    )
    parser.add_argument(
        "--baud-rate",
        type=int,
        help="serial baud rate for a native ASRL connection (must match the instrument)",
    )
    return parser.parse_args(argv)


def configure_and_measure(instrument: SR830) -> None:
    """Apply a representative setup and print one simultaneous measurement."""
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


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.resource_name is None:
        with VirtualSR830() as virtual_instrument:
            virtual_instrument.connect("GPIB0::8::INSTR")
            # Demodulated RMS X/Y input components in volts; hardware is never driven.
            virtual_instrument.set_signal(0.003, 0.004)
            configure_and_measure(virtual_instrument)
        return

    import pyvisa

    manager = pyvisa.ResourceManager(args.visa_backend or "")
    try:
        serial_kwargs: dict[str, int] = {}
        if args.baud_rate is not None:
            serial_kwargs["baud_rate"] = args.baud_rate
        with SR830() as hardware_instrument:
            hardware_instrument.connect(
                args.resource_name,
                resource_manager=manager,
                output_interface=args.output_interface,
                **serial_kwargs,
            )
            configure_and_measure(hardware_instrument)
    finally:
        # SR830's context has disconnected the resource before manager closes.
        manager.close()


main()
