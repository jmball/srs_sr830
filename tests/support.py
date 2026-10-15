"""Instrument connection and restoration helpers shared by test fixtures."""

import argparse
import math

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Any

import pyvisa
from pyvisa.constants import Parity, StopBits

from sr830 import SR830
from virtual_sr830 import VirtualSR830


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


@dataclass(frozen=True)
class InstrumentOptions:
    resource_name: str | None = None
    visa_backend: str | None = None
    output_interface: int | None = None
    visa_timeout: int = 5000
    baud_rate: int | None = None
    data_bits: int | None = None
    parity: str | None = None
    stop_bits: float | None = None
    write_termination: str | None = None

    def resource_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"timeout": self.visa_timeout}
        for name in ("baud_rate", "data_bits"):
            value = getattr(self, name)
            if value is not None:
                kwargs[name] = value
        if self.parity is not None:
            kwargs["parity"] = Parity[self.parity]
        if self.stop_bits is not None:
            kwargs["stop_bits"] = {
                1.0: StopBits.one,
                1.5: StopBits.one_and_a_half,
                2.0: StopBits.two,
            }[self.stop_bits]
        if self.write_termination is not None:
            kwargs["write_termination"] = {
                "LF": "\n",
                "CR": "\r",
                "CRLF": "\r\n",
            }[self.write_termination]
        return kwargs


@contextmanager
def open_instrument(options: InstrumentOptions) -> Iterator[SR830 | VirtualSR830]:
    """Use a virtual instrument by default; a requested VISA failure stays a failure."""
    if options.resource_name is None:
        with VirtualSR830() as virtual:
            virtual.connect("ASRL1::INSTR", output_interface=options.output_interface)
            yield virtual
        return

    # This fixture owns the manager it creates; the driver only owns its resource.
    manager = pyvisa.ResourceManager(options.visa_backend or "")
    try:
        with SR830() as instrument:
            instrument.connect(
                options.resource_name,
                resource_manager=manager,
                output_interface=options.output_interface,
                **options.resource_kwargs(),
            )
            identity = instrument.idn
            fields = identity.split(",")
            assert len(fields) >= 2 and fields[1].strip().upper() == "SR830", (
                f"Expected an SR830 at {options.resource_name}, received {identity!r}."
            )
            yield instrument
    finally:
        manager.close()


@contextmanager
def preserve_settings(instrument: object, *names: str) -> Iterator[None]:
    """Restore each changed property even after assertions or other cleanup fail."""
    with ExitStack() as cleanup:
        for name in names:
            cleanup.callback(setattr, instrument, name, getattr(instrument, name))
        yield
