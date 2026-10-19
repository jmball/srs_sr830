"""Stateful SR830 simulation sharing the hardware driver's public interface.

Protocol reference: https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf.
The signal is a complex demodulated RMS amplitude in V (voltage mode) or A
(current mode). Filter settling and acquisition use an injectable monotonic clock.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import math
import struct
import time
from typing import Any

import pyvisa
from pyvisa.constants import InterfaceType

from sr830 import SR830
from sr830._connection import connection_kwargs, resolve_output_interface
from sr830.settings import (
    AuxiliaryChannel,
    OutputInterface,
    LiaStatusFlag,
    StatusRegister,
    _time_constant_seconds,
    _validate_enum,
    _validate_register_value,
)
from ._simulation import Simulation


class VirtualSR830(SR830):
    """SR830 state/signal/acquisition simulator, without VISA or real-time sleeps.

    Public I/O requires connect(), just as on hardware.

    Parameters
    ----------
    clock : callable, optional
        Monotonic seconds; defaults to time.monotonic. Use a fixed clock for
        deterministic tests and advance_time() to move simulated time forward.
    signal : callable, optional
        Complex demodulated RMS input at a given simulation time, in V for
        voltage inputs or A for current inputs. With no callback, set_signal()
        configures a constant input (initially 1 mV on X, zero on Y).
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        signal: Callable[[float], complex] | None = None,
    ) -> None:
        super().__init__()
        self._connected = False
        self._simulation = Simulation(clock, signal)
        self._virtual_timeout = 10.0

    def __enter__(self) -> VirtualSR830:
        return self

    def connect(
        self,
        resource_name: str,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        output_interface: OutputInterface | int | None = None,
        **resource_kwargs: Any,
    ) -> None:
        """Connect the simulator using the hardware interface/framing rules.

        A supplied manager is used only to resolve resource names; it stays
        caller-owned. No VISA resource is opened. Settings persist on reconnect.
        """
        if self._connected:
            raise RuntimeError("Instrument is already connected; disconnect first.")
        if resource_manager is not None:
            interface_type = resource_manager.resource_info(
                resource_name
            ).interface_type
        else:
            name = pyvisa.rname.parse_resource_name(resource_name)
            interface_type = InterfaceType[name.interface_type.lower()]
        interface = resolve_output_interface(interface_type, output_interface)
        connection_kwargs(interface, resource_kwargs, interface_type=interface_type)
        self._simulation.settings["OUTX"] = interface
        self._simulation.enables = {name: 255 for name in self._simulation.enables}
        self._io_desynchronized = False
        self._connected = True
        try:
            self.check_errors()
        except BaseException:
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Return to local mode and disconnect; repeated calls are harmless."""
        if self._connected:
            self._connected = False
            self._fast_running = False
            try:
                self._simulation.update()
            finally:
                self._simulation.settings["LOCL"] = 0

    def _check_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Instrument is not connected.")

    def _raw_write(self, command: str) -> None:
        self._check_connected()
        self._check_synchronized()
        self._simulation.write(command)

    def _raw_query(self, command: str) -> str:
        self._check_connected()
        if self._fast_running:
            raise RuntimeError("Stop fast transfer before issuing text queries.")
        self._check_synchronized()
        delay = max(0.0, self._simulation.busy_until - self._simulation.now())
        self.advance_time(min(delay, self._virtual_timeout))
        if delay > self._virtual_timeout:
            self._io_desynchronized = True
            raise pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_timeout)
        return self._simulation.query(command)

    def _raw_query_ascii_values(self, command: str) -> list[str]:
        return self._raw_query(command).split(",")

    def _raw_read_buffer_bytes(self, command: str, size: int) -> bytes:
        self._check_connected()
        self._check_synchronized()
        data = self._simulation.buffer_bytes(command)
        if len(data) != size:
            raise OSError("Incomplete virtual binary response.")
        return data

    def _recover_after_timeout(self) -> bool:
        # The model produces complete responses synchronously and has no stale bytes.
        self._check_connected()
        return True

    @property
    def output_interface(self) -> int:
        return int(self._query("OUTX?"))

    @output_interface.setter
    def output_interface(self, interface: OutputInterface | int) -> None:
        _validate_enum(interface, OutputInterface)
        if self._fast_running:
            raise RuntimeError(
                "Stop fast transfer before changing the output interface."
            )
        if interface not in (0, 1):
            raise ValueError("Output interface must be 0 (RS232) or 1 (GPIB).")
        self._write(f"OUTX {int(interface)}")

    def serial_poll(self) -> int:
        """Read status without clearing events, acknowledging a service request."""
        self._check_connected()
        return self._simulation.status(acknowledge=True)

    @contextmanager
    def _io_timeout(self, seconds: float) -> Iterator[None]:
        self._check_connected()
        previous = self._virtual_timeout
        self._virtual_timeout = seconds
        try:
            yield
        finally:
            self._virtual_timeout = previous

    def wait_until_ready(
        self, timeout: float = 10.0, *, poll_interval: float = 0.01
    ) -> None:
        """Advance simulated time until completion, or raise TimeoutError."""
        self._check_connected()
        self._validate_wait(timeout, poll_interval)
        delay = max(0.0, self._simulation.busy_until - self._simulation.now())
        self.advance_time(min(delay, timeout))
        if delay > timeout:
            raise TimeoutError("Timed out waiting for virtual command completion.")

    def wait_for_settling(
        self, timeout: float = 60.0, *, time_constants: float = 10.0
    ) -> None:
        """Advance command-completion and filter-settling time without sleeping."""
        self._validate_wait(timeout, time_constants)
        started = self._simulation.now()
        self.wait_until_ready(timeout)
        delay = time_constants * _time_constant_seconds(self.time_constant)
        if self._simulation.now() - started + delay > timeout:
            raise TimeoutError("Settling requires more time than the supplied timeout.")
        self.advance_time(delay)

    def _discard_fast_data(self) -> None:
        self._check_connected()
        self._simulation.fast.clear()

    def _read_fast_bytes(self, size: int) -> bytes:
        self._check_connected()
        deadline = self._simulation.now() + self._virtual_timeout
        result = bytearray()
        while len(result) < size:
            self._simulation.update()
            if self._simulation.fast:
                result.extend(struct.pack("<hh", *self._simulation.fast.popleft()))
                continue
            now = self._simulation.now()
            remaining = deadline - now
            if (
                remaining <= 0
                or not self._simulation.running
                or self._simulation.settings["SRAT"] == 14
            ):
                raise TimeoutError("No virtual fast-transfer samples before timeout.")
            rate = 0.0625 * 2 ** int(self._simulation.settings["SRAT"])
            delay = max(0.0, self._simulation.last_sample + 1 / rate - now)
            self.advance_time(min(max(delay, 1e-9), remaining))
        return bytes(result)

    def advance_time(self, seconds: float) -> None:
        """Advance the simulation clock and acquisition without wall-clock sleep."""
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("seconds must be finite and nonnegative.")
        self._simulation.offset_time += seconds
        self._simulation.update()

    def set_signal(self, x: float, y: float = 0.0, *, settle: bool = False) -> None:
        """Set constant demodulated RMS input in V or A, before phase/offset/expand.

        Replaces a time-dependent signal callback supplied at construction.

        Parameters
        ----------
        x, y : float
            Input components, finite RMS amplitudes in V or A. By default the
            measured output approaches these through the selected low-pass filter.
        settle : bool, optional
            Initialize the filter immediately at this input when True.
        """
        if not isinstance(settle, bool):
            raise ValueError("settle must be a bool.")
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Signal components must be finite.")
        self._simulation.update()
        self._simulation.signal = None
        self._simulation.input = complex(x, y)
        if settle:
            self._simulation.filters = [complex(x, y)] * 4

    def set_aux_input(self, channel: AuxiliaryChannel | int, voltage: float) -> None:
        """Apply a simulated auxiliary input voltage independently of aux outputs."""
        _validate_enum(channel, AuxiliaryChannel)
        if (
            channel not in (1, 2, 3, 4)
            or not math.isfinite(voltage)
            or not -10.5 <= voltage <= 10.5
        ):
            raise ValueError("Invalid auxiliary input channel or voltage.")
        self._simulation.aux_inputs[int(channel) - 1] = voltage

    def set_external_reference(self, frequency: float, *, locked: bool = True) -> None:
        """Set the simulated external reference; unlocked frequency reads zero."""
        if not math.isfinite(frequency) or not 0.001 <= frequency <= 102000:
            raise ValueError("External frequency must be in range 0.001 to 102000 Hz.")
        if not isinstance(locked, bool):
            raise ValueError("locked must be a bool.")
        self._simulation.update()
        self._simulation.external_frequency = frequency
        self._simulation.external_locked = locked
        if not locked:
            self._simulation.registers["lia_status"] |= int(
                LiaStatusFlag.REFERENCE_UNLOCK
            )

    def inject_status(self, register: StatusRegister | str, value: int) -> None:
        """Latch simulated error/event flags; serial-poll state is computed."""
        _validate_register_value(register, value, True)
        if register not in ("standard_event", "error", "lia_status"):
            raise ValueError(
                "Inject an event register, not the computed serial-poll byte."
            )
        self._simulation.registers[register] |= int(value)
        self._simulation.srq_acknowledged = False
