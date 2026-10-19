"""Stanford Research Systems SR830 lock-in amplifier (LIA) control library.

The full instrument manual, including the programming guide, can be found at
https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from types import TracebackType
from typing import Any

import logging
import struct
import math
import time
import warnings

import pyvisa
from pyvisa.constants import SerialTermination
from pyvisa.resources import MessageBasedResource, SerialInstrument

from .exceptions import InstrumentError, _check_registers
from ._connection import connection_kwargs, resolve_output_interface
from .settings import (
    AuxiliaryChannel,
    Channel,
    Channel1Display,
    Channel1Ratio,
    Channel2Display,
    Channel2Ratio,
    DataTransferMode,
    EndOfBufferMode,
    ErrorBit,
    ErrorFlag,
    FrontPanelOutputSource,
    GpibOverrideRemote,
    InputConfiguration,
    InputCoupling,
    InputShieldGrounding,
    LiaStatusBit,
    LiaStatusFlag,
    LineNotchFilter,
    LocalMode,
    LowPassFilterSlope,
    MeasurementParameter,
    OutputExpansion,
    OutputInterface,
    OutputParameter,
    ReferenceSource,
    ReferenceTrigger,
    ReserveMode,
    SampleRate,
    Sensitivity,
    SerialPollBit,
    SerialPollFlag,
    StandardEventBit,
    StandardEventFlag,
    StatusRegister,
    SwitchState,
    SynchronousFilter,
    TimeConstant,
    TriggerStartMode,
    _ENABLE_REGISTER_COMMANDS,
    _STATUS_REGISTER_COMMANDS,
    _require_integer,
    _time_constant_seconds,
    _validate_enum,
    _validate_register_bit,
    _validate_register_value,
)


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_NOT_CONNECTED_MESSAGE = "Instrument is not connected."


class SR830:
    """Stanford Research Systems SR830 LIA instrument.

    Use connect() to open a VISA connection and disconnect() to close it.
    The resource is stored privately in _instr; driver-owned I/O helpers raise
    RuntimeError when disconnected. Normal writes and queries check command and
    device errors; measurement readers also check overload/unlock status. Event
    register reads clear latched events. FAST diagnostics are deferred until stop.
    """

    def __init__(self) -> None:
        self._instr: MessageBasedResource | None = None
        self._fast_running = False
        self._io_desynchronized = False

    def _raw_write(self, command: str) -> None:
        """Send a command to the connected instrument."""
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        self._check_synchronized()
        try:
            self._instr.write(command)
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                self._io_desynchronized = True
            raise

    def _raw_query(self, command: str) -> str:
        """Send a command and read its text response."""
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        if self._fast_running:
            raise RuntimeError("Stop fast transfer before issuing text queries.")
        self._check_synchronized()
        try:
            return self._instr.query(command)
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                self._io_desynchronized = True
            raise

    def _raw_query_ascii_values(self, command: str) -> list[str]:
        """Query ASCII fields, preserving empty trailing fields for buffer parsing."""
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        if self._fast_running:
            raise RuntimeError("Stop fast transfer before issuing text queries.")
        self._check_synchronized()
        return list(
            self._instr.query_ascii_values(
                command, converter=lambda value: value, container=list
            )
        )

    def _raw_read_buffer_bytes(self, command: str, size: int) -> bytes:
        """Read a headerless SR830 buffer without interpreting CR/LF as framing."""
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        self._check_synchronized()
        if self._fast_running:
            raise RuntimeError("Stop fast transfer before issuing buffer queries.")
        resource = self._instr
        termination = resource.read_termination
        serial_end = (
            resource.end_input if isinstance(resource, SerialInstrument) else None
        )
        try:
            resource.read_termination = None
            if isinstance(resource, SerialInstrument):
                resource.end_input = SerialTermination.none
            resource.write(command)
            data = resource.read_bytes(size, break_on_termchar=False)
            if len(data) != size:
                raise OSError(
                    f"Incomplete binary response: expected {size} bytes, received {len(data)}."
                )
            return data
        finally:
            try:
                if isinstance(resource, SerialInstrument) and serial_end is not None:
                    resource.end_input = serial_end
            finally:
                resource.read_termination = termination

    def __enter__(self) -> SR830:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the runtime context related to this object."""
        self.disconnect()

    def connect(
        self,
        resource_name: str,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        output_interface: OutputInterface | int | None = None,
        **resource_kwargs: Any,
    ) -> None:
        """Open and initialize a VISA connection without resetting the instrument.

        Parameters
        ----------
        resource_name : str
            VISA resource name or alias.
        resource_manager : pyvisa.ResourceManager, optional
            Manager to use, or the default backend's manager. The VISA resource
            retains it. Caller-supplied managers remain caller-owned. Managers
            are never closed here because PyVISA shares backend sessions.
        output_interface : OutputInterface or int, optional
            Instrument-side response interface: 0 (RS232) or 1 (GPIB). Inferred
            for ASRL and GPIB VISA resources. Required for ambiguous resources,
            including TCP/IP adapters. An explicit value overrides inference.
        resource_kwargs : Any
            VISA opening options and resource attributes. Read termination must
            be CR for RS232 or LF for GPIB. Write termination defaults to LF; CR and CRLF are
            also accepted for serial, and CRLF for GPIB. Native GPIB resources
            can use EOI alone with send_end=True. Conflicts are rejected. Baud rate and parity must match the front panel.

        Notes
        -----
        The driver owns the opened resource. A second connect raises RuntimeError
        until disconnect is called. Initialization selects the response interface,
        and enables status registers before checking errors and storing _instr.
        Set local_mode explicitly after connecting to select remote mode or local lockout.
        Failures close the resource and leave the instance disconnected; commands
        already sent to the instrument cannot be rolled back. Call reset()
        explicitly if a factory reset is wanted.
        """
        if self._instr is not None:
            raise RuntimeError("Instrument is already connected; disconnect first.")
        manager = (
            resource_manager
            if resource_manager is not None
            else pyvisa.ResourceManager()
        )
        interface_type = manager.resource_info(resource_name).interface_type
        interface = resolve_output_interface(interface_type, output_interface)
        kwargs = connection_kwargs(
            interface, resource_kwargs, interface_type=interface_type
        )
        opening_kwargs = {
            key: kwargs.pop(key)
            for key in ("access_mode", "open_timeout", "resource_pyclass")
            if key in kwargs
        }
        logger.debug(
            "Opening SR830 resource %s with %s output",
            resource_name,
            OutputInterface(interface).name,
        )
        resource = manager.open_resource(resource_name, **opening_kwargs)
        try:
            if not isinstance(resource, MessageBasedResource):
                raise TypeError("SR830 requires a message-based VISA resource.")
            for key, value in kwargs.items():
                if not hasattr(resource, key):
                    raise ValueError(f"{key!r} is not a valid VISA resource attribute.")
                setattr(resource, key, value)
            resource.write(f"OUTX {interface}")
            for command in _ENABLE_REGISTER_COMMANDS.values():
                resource.write(f"{command} 255")
            _check_registers(resource.query, ("*ESR?", "ERRS?"), "connect()")
        except BaseException:
            # Preserve the initialization error even if close also fails.
            with suppress(Exception):
                resource.close()
            raise
        self._instr = resource
        self._io_desynchronized = False
        logger.debug("SR830 connection initialized: %s", resource_name)

    def disconnect(self) -> None:
        """Return to local mode and close the resource; repeated calls are harmless.

        Always clear the connection, even if returning to local mode or closing
        fails. Resource managers remain open because their sessions may be shared.
        """
        resource = self._instr
        if resource is None:
            return
        self._instr = None
        self._fast_running = False
        logger.debug("Disconnecting SR830 resource %s", resource)
        try:
            resource.write("LOCL 0")
        except pyvisa.errors.InvalidSession:
            # The underlying VISA resource may already have been closed.
            resource.close()
        except BaseException:
            with suppress(Exception):
                resource.close()
            raise
        else:
            resource.close()
        logger.debug("SR830 resource disconnected: %s", resource)

    def enable_all_status_bytes(self) -> None:
        """Enable all status bytes."""
        registers = ["standard_event", "serial_poll", "error", "lia_status"]
        for register in registers:
            self.set_enable_register(register, 255, decimal=True)

    def _check_synchronized(self) -> None:
        if self._io_desynchronized:
            raise RuntimeError(
                "Response framing is uncertain after an I/O failure; disconnect and reconnect."
            )

    def check_errors(self, *, operation: str = "check_errors()") -> None:
        """Raise InstrumentError for command/execution and device faults.

        Reads *ESR? and ERRS? directly, independently of enable masks. These
        reads clear latched events, including non-error events such as power-on.
        Faults may predate the operation. Measurement overload/unlock is checked
        separately by check_measurement_status(). Automatic checks are deferred
        during FAST; explicit checks raise RuntimeError until streaming stops.
        """
        _check_registers(self._raw_query, ("*ESR?", "ERRS?"), operation)

    def check_measurement_status(
        self, *, operation: str = "check_measurement_status()"
    ) -> None:
        """Raise InstrumentError for latched overload or reference-unlock faults.

        Reads and clears LIAS?, including ordinary events such as triggers.
        Measurement readers call this automatically. Configuration writes leave
        this register alone, allowing callers to fix an overload or unlock.
        """
        _check_registers(self._raw_query, ("LIAS?",), operation)

    def _write(self, command: str) -> None:
        self._raw_write(command)
        if not self._fast_running:
            self.check_errors(operation=command)

    def _diagnose_timeout(
        self, command: str, failure: pyvisa.errors.VisaIOError
    ) -> None:
        # A delayed response could otherwise be mistaken for a status register.
        self._io_desynchronized = True
        try:
            with self._io_timeout(1.0):
                if not self._recover_after_timeout():
                    return
                self._io_desynchronized = False
                self.check_errors(operation=command)
        except InstrumentError as exc:
            raise exc from failure
        except Exception:
            self._io_desynchronized = True
            # An inconclusive diagnostic must preserve the original transport error.

    def _recover_after_timeout(self) -> bool:
        """Discard pending output only on native GPIB, where device clear is defined."""
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        if self._instr.interface_type != pyvisa.constants.InterfaceType.gpib:
            return False
        self._instr.clear()
        return True

    def _query(self, command: str) -> str:
        try:
            result = self._raw_query(command)
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                self._diagnose_timeout(command, exc)
            raise
        self.check_errors(operation=command)
        return result

    def _query_ascii_values(self, command: str) -> list[str]:
        try:
            result = self._raw_query_ascii_values(command)
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                self._diagnose_timeout(command, exc)
            raise
        self.check_errors(operation=command)
        return result

    def _read_buffer_bytes(self, command: str, size: int) -> bytes:
        try:
            result = self._raw_read_buffer_bytes(command, size)
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                self._diagnose_timeout(command, exc)
            raise
        except OSError:
            self._io_desynchronized = True
            raise
        # The raw reader has restored text framing before diagnostics.
        self.check_errors(operation=command)
        return result

    # --- Reference and phase commands ---
    @property
    def reference_phase_shift(self) -> float:
        """Get the reference phase shift.

        Returns
        -------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        return float(self._query("PHAS?"))

    @reference_phase_shift.setter
    def reference_phase_shift(self, phase_shift: float) -> None:
        """Set the reference phase shift.

        Parameters
        ----------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        if (phase_shift >= -360) and (phase_shift <= 720):
            self._write(f"PHAS {phase_shift}")
        else:
            raise ValueError(
                f"Invalid phase shift: {phase_shift}. Must be in range -360 - 720 "
                + "degrees."
            )

    @property
    def reference_source(self) -> int:
        """Get the reference source.

        Returns an integer code; use ReferenceSource(code) for its named setting.

        Returns
        -------
        source : {0, 1}
            Refernce source:

                * 0 : external
                * 1 : internal
        """
        return int(self._query("FMOD?"))

    @reference_source.setter
    def reference_source(self, source: ReferenceSource | int) -> None:
        """Set the reference source.

        Parameters
        ----------
        source : ReferenceSource or int
            Refernce source:

                * 0 : external
                * 1 : internal
        """
        _validate_enum(source, ReferenceSource)
        if source in [0, 1]:
            self._write(f"FMOD {int(source)}")
        else:
            raise ValueError(
                f"Invalid reference source: {source}. Must be 0 (external) or 1 "
                + "(internal)."
            )

    @property
    def reference_frequency(self) -> float:
        """Get the reference frequency.

        Returns
        -------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        return float(self._query("FREQ?"))

    @reference_frequency.setter
    def reference_frequency(self, freq: float) -> None:
        """Set the frequency of the internal oscillator.

        Parameters
        ----------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        if (freq >= 0.001) and (freq <= 102000):
            self._write(f"FREQ {freq}")
        else:
            raise ValueError(
                f"Invalid reference frequency: {freq}. Must be in range 0.001 - 102000 "
                + "Hz."
            )

    @property
    def reference_trigger(self) -> int:
        """Get the reference trigger type when using external ref.

        Returns an integer code; use ReferenceTrigger(code) for its named setting.

        Returns
        -------
        trigger : {0, 1, 2}
            Trigger type:

                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge
        """
        return int(self._query("RSLP?"))

    @reference_trigger.setter
    def reference_trigger(self, trigger: ReferenceTrigger | int) -> None:
        """Set the reference trigger type when using external ref.

        Parameters
        ----------
        trigger : ReferenceTrigger or int
            Trigger type:

                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge
        """
        _validate_enum(trigger, ReferenceTrigger)
        if trigger in [0, 1, 2]:
            self._write(f"RSLP {int(trigger)}")
        else:
            raise ValueError(
                f"Invalid trigger type: {trigger}. Must be 0 (zero crossing), 1 "
                + "(rising edge), or 2 (falling edge)."
            )

    @property
    def harmonic(self) -> int:
        """Get detection harmonic.

        Returns
        -------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        return int(self._query("HARM?"))

    @harmonic.setter
    def harmonic(self, harmonic: int) -> None:
        """Set detection harmonic.

        Parameters
        ----------
        harmonic : int
            Detection harmonic, 1 =< harmonic =< 19999.
        """
        _require_integer(harmonic, "harmonic")
        if (harmonic >= 1) and (harmonic <= 19999):
            self._write(f"HARM {harmonic}")
        else:
            raise ValueError(
                f"Invalid detection harmonic: {harmonic}. Must be in range 1 - 19999."
            )

    @property
    def sine_amplitude(self) -> float:
        """Get the amplitude of the sine output.

        Returns
        -------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        return float(self._query("SLVL?"))

    @sine_amplitude.setter
    def sine_amplitude(self, amplitude: float) -> None:
        """Set the amplitude of the sine output.

        Parameters
        ----------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        if (amplitude >= 0.004) and (amplitude <= 5):
            self._write(f"SLVL {amplitude}")
        else:
            raise ValueError(
                f"Invalid sine output amplitude: {amplitude}. Must be in range 0.004 -"
                + " 5 volts."
            )

    @property
    def input_configuration(self) -> int:
        """Set the input configuration.

        Returns an integer code; use InputConfiguration(code) for its named setting.

        Returns
        -------
        config : {0, 1, 2, 3}
            Input configuration:

                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)
        """
        return int(self._query("ISRC?"))

    @input_configuration.setter
    def input_configuration(self, config: InputConfiguration | int) -> None:
        """Set the input configuration.

        Parameters
        ----------
        config : InputConfiguration or int
            Input configuration:

                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)
        """
        _validate_enum(config, InputConfiguration)
        if config in range(4):
            self._write(f"ISRC {int(config)}")
        else:
            raise ValueError(
                f"Invalid input configuration: {config}. Must be 0 (A), 1 (A-B), 2 "
                + "(I 1MOhm), or 3 (I 100MOhm)."
            )

    @property
    def input_shield_grounding(self) -> int:
        """Get input shield grounding.

        Returns an integer code; use InputShieldGrounding(code) for its named setting.

        Returns
        -------
        grounding : {0, 1}
            Input shield grounding:

                * 0 : Float
                * 1 : Ground
        """
        return int(self._query("IGND?"))

    @input_shield_grounding.setter
    def input_shield_grounding(self, grounding: InputShieldGrounding | int) -> None:
        """Set input shield grounding.

        Parameters
        ----------
        grounding : InputShieldGrounding or int
            Input shield grounding:

                * 0 : Float
                * 1 : Ground
        """
        _validate_enum(grounding, InputShieldGrounding)
        if grounding in [0, 1]:
            self._write(f"IGND {int(grounding)}")
        else:
            raise ValueError(
                f"Invalid input shield grounding: {grounding}. Must be 0 (float) or 1"
                + " (ground)."
            )

    @property
    def input_coupling(self) -> int:
        """Get input coupling.

        Returns an integer code; use InputCoupling(code) for its named setting.

        Returns
        -------
        coupling : {0, 1}
            Input coupling:

                * 0 : AC
                * 1 : DC
        """
        return int(self._query("ICPL?"))

    @input_coupling.setter
    def input_coupling(self, coupling: InputCoupling | int) -> None:
        """Set input coupling.

        Parameters
        ----------
        coupling : InputCoupling or int
            Input coupling:

                * 0 : AC
                * 1 : DC
        """
        _validate_enum(coupling, InputCoupling)
        if coupling in [0, 1]:
            self._write(f"ICPL {int(coupling)}")
        else:
            raise ValueError(
                f"Invalid input coupling: {coupling}. Must be 0 (AC) or 1 (DC)."
            )

    @property
    def line_notch_filter_status(self) -> int:
        """Get input line notch filter status.

        Returns an integer code; use LineNotchFilter(code) for its named setting.

        Returns
        -------
        status : {0, 1, 2, 3}
            Input line notch filter status:

                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in
        """
        return int(self._query("ILIN?"))

    @line_notch_filter_status.setter
    def line_notch_filter_status(self, status: LineNotchFilter | int) -> None:
        """Set input line notch filter status.

        Parameters
        ----------
        status : LineNotchFilter or int
            Input line notch filter status:

                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in
        """
        _validate_enum(status, LineNotchFilter)
        if status in range(4):
            self._write(f"ILIN {int(status)}")
        else:
            raise ValueError(
                f"Invalid line notch filter status: {status}. Must be 0 (no filters), "
                + "1 (line notch in), 2 (2 x line notch in), or 3 (both line notch in)"
                + "."
            )

    # --- Gain and time constant commands ---

    @property
    def sensitivity(self) -> int:
        """Get sensitivity.

        Returns an integer code; use Sensitivity(code) for its named setting.

        Returns
        -------
        sensitivity : {0 - 26}
            RMS full-scale amplitude, in V for voltage inputs or microamps
            for current inputs (not gain):

                * 0 : 2e-9
                * 1 : 5e-9
                * 2 : 10e-9
                * 3 : 20e-9
                * 4 : 50e-9
                * 5 : 100e-9
                * 6 : 200e-9
                * 7 : 500e-9
                * 8 : 1e-6
                * 9 : 2e-6
                * 10 : 5e-6
                * 11 : 10e-6
                * 12 : 20e-6
                * 13 : 50e-6
                * 14 : 100e-6
                * 15 : 200e-6
                * 16 : 500e-6
                * 17 : 1e-3
                * 18 : 2e-3
                * 19 : 5e-3
                * 20 : 10e-3
                * 21 : 20e-3
                * 22 : 50e-3
                * 23 : 100e-3
                * 24 : 200e-3
                * 25 : 500e-3
                * 26 : 1
        """
        return int(self._query("SENS?"))

    @sensitivity.setter
    def sensitivity(self, sensitivity: Sensitivity | int) -> None:
        """Set sensitivity.

        Parameters
        ----------
        sensitivity : Sensitivity or int
            RMS full-scale amplitude (not gain), in V for voltage inputs or
            microamps for current inputs. Names use x<number><SI prefix>,
            with u for micro (x1u) and x1 for the unity multiplier:

                * 0 : 2e-9
                * 1 : 5e-9
                * 2 : 10e-9
                * 3 : 20e-9
                * 4 : 50e-9
                * 5 : 100e-9
                * 6 : 200e-9
                * 7 : 500e-9
                * 8 : 1e-6
                * 9 : 2e-6
                * 10 : 5e-6
                * 11 : 10e-6
                * 12 : 20e-6
                * 13 : 50e-6
                * 14 : 100e-6
                * 15 : 200e-6
                * 16 : 500e-6
                * 17 : 1e-3
                * 18 : 2e-3
                * 19 : 5e-3
                * 20 : 10e-3
                * 21 : 20e-3
                * 22 : 50e-3
                * 23 : 100e-3
                * 24 : 200e-3
                * 25 : 500e-3
                * 26 : 1
        """
        _validate_enum(sensitivity, Sensitivity)
        if sensitivity in range(27):
            self._write(f"SENS {int(sensitivity)}")
        else:
            raise ValueError(
                f"Invalid sensitivity: {sensitivity}. Must be an integer in range 0 - "
                + "26."
            )

    @property
    def reserve_mode(self) -> int:
        """Get reserve mode.

        Returns an integer code; use ReserveMode(code) for its named setting.

        Returns
        -------
        mode : {0, 1, 2}
            Reserve mode:

                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise
        """
        return int(self._query("RMOD?"))

    @reserve_mode.setter
    def reserve_mode(self, mode: ReserveMode | int) -> None:
        """Set reserve mode.

        Parameters
        ----------
        mode : ReserveMode or int
            Reserve mode:

                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise
        """
        _validate_enum(mode, ReserveMode)
        if mode in range(3):
            self._write(f"RMOD {int(mode)}")
        else:
            raise ValueError(
                f"Invalid reserve mode: {mode}. Must be 0 (high), 1 (normal), or 2 "
                + "(low)."
            )

    @property
    def time_constant(self) -> int:
        """Get time constant.

        Returns an integer code; use TimeConstant(code) for its named setting.

        Returns
        -------
        tc : {0 - 19}
            Time constant in s:

                * 0 : 10e-6
                * 1 : 30e-6
                * 2 : 100e-6
                * 3 : 300e-6
                * 4 : 1e-3
                * 5 : 3e-3
                * 6 : 10e-3
                * 7 : 30e-3
                * 8 : 100e-3
                * 9 : 300e-3
                * 10 : 1
                * 11 : 3
                * 12 : 10
                * 13 : 30
                * 14 : 100
                * 15 : 300
                * 16 : 1e3
                * 17 : 3e3
                * 18 : 10e3
                * 19 : 30e3
        """
        return int(self._query("OFLT?"))

    @time_constant.setter
    def time_constant(self, tc: TimeConstant | int) -> None:
        """Set time constant.

        Parameters
        ----------
        tc : TimeConstant or int
            Time constant in s:

                * 0 : 10e-6
                * 1 : 30e-6
                * 2 : 100e-6
                * 3 : 300e-6
                * 4 : 1e-3
                * 5 : 3e-3
                * 6 : 10e-3
                * 7 : 30e-3
                * 8 : 100e-3
                * 9 : 300e-3
                * 10 : 1
                * 11 : 3
                * 12 : 10
                * 13 : 30
                * 14 : 100
                * 15 : 300
                * 16 : 1e3
                * 17 : 3e3
                * 18 : 10e3
                * 19 : 30e3
        """
        _validate_enum(tc, TimeConstant)
        if tc in range(20):
            self._write(f"OFLT {int(tc)}")
        else:
            raise ValueError(
                f"Invalid time constant: {tc}. Must be an integer in range 0 - 19."
            )

    @property
    def lowpass_filter_slope(self) -> int:
        """Get the low pass filter slope.

        Returns an integer code; use LowPassFilterSlope(code) for its named setting.

        Returns
        -------
        slope : {0, 1, 2, 3}
            Low pass filter slope in dB/oct:

                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24
        """
        return int(self._query("OFSL?"))

    @lowpass_filter_slope.setter
    def lowpass_filter_slope(self, slope: LowPassFilterSlope | int) -> None:
        """Set the low pass filter slope.

        Parameters
        ----------
        slope : LowPassFilterSlope or int
            Low pass filter slope in dB/oct:

                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24
        """
        _validate_enum(slope, LowPassFilterSlope)
        if slope in range(4):
            self._write(f"OFSL {int(slope)}")
        else:
            raise ValueError(
                f"Invalid low-pass filter slope: {slope}. Must be 0 (6 dB/oct), 1 "
                + "(12 dB/oct), 2 (18 dB/oct), or 3 (24 dB/oct)."
            )

    @property
    def sync_filter_status(self) -> int:
        """Get synchronous filter status.

        Returns an integer code; use SynchronousFilter(code) for its named setting.

        Returns
        -------
        status : {0, 1}
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz
        """
        return int(self._query("SYNC?"))

    @sync_filter_status.setter
    def sync_filter_status(self, status: SynchronousFilter | int) -> None:
        """Set synchronous filter status.

        Parameters
        ----------
        status : SynchronousFilter or int
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz
        """
        _validate_enum(status, SynchronousFilter)
        if status in [0, 1]:
            self._write(f"SYNC {int(status)}")
        else:
            raise ValueError(
                f"Invalid synchronous filter status: {status}. Must be 0 (off) or 1 "
                + "(below 200 Hz)."
            )

    # --- Display and output commands ---

    @property
    def output_interface(self) -> int:
        """Get the output communication interface.

        Returns an integer code; use OutputInterface(code) for its named setting.

        Returns
        -------
        interface : {0, 1}
            Output communication interface:

                * 0 : RS232
                * 1 : GPIB
        """
        return int(self._query("OUTX?"))

    @output_interface.setter
    def output_interface(self, interface: OutputInterface | int) -> None:
        """Set the output communication interface.

        This command should be sent before any query commands to direct the
        responses to the interface in use.

        Parameters
        ----------
        interface : OutputInterface or int
            Output communication interface:

                * 0 : RS232
                * 1 : GPIB
        """
        _validate_enum(interface, OutputInterface)
        if self._fast_running:
            raise RuntimeError(
                "Stop fast transfer before changing the output interface."
            )
        if interface in [0, 1]:
            if self._instr is None:
                raise RuntimeError(_NOT_CONNECTED_MESSAGE)
            resource = self._instr
            previous = resource.read_termination
            try:
                resource.read_termination = "\r" if interface == 0 else "\n"
                self._raw_write(f"OUTX {int(interface)}")
            except BaseException:
                with suppress(Exception):
                    resource.read_termination = previous
                raise
            self.check_errors(operation=f"OUTX {int(interface)}")
        else:
            raise ValueError(
                f"Invalid output interface: {interface}. Must be 0 (RS232) or 1 "
                + "(GPIB)."
            )

    def set_display(
        self,
        channel: Channel | int,
        display: Channel1Display | Channel2Display | int = 1,
        ratio: Channel1Ratio | Channel2Ratio | int = 0,
    ) -> None:
        """Set a channel display configuration.

        Parameters
        ----------
        channel : Channel or int
            Channel:

                * 1 : CH1
                * 2 : CH2

        display : Channel1Display | Channel2Display or int
            Display parameter for CH1:

                * 0 : X
                * 1 : R
                * 2 : X Noise
                * 3 : Aux In 1
                * 4 : Aux In 2;

            Display parameter for CH2:

                * 0 : Y
                * 1 : Phase
                * 2 : Y Noise
                * 3 : Aux In 3
                * 4 : Aux In 4

        ratio : Channel1Ratio | Channel2Ratio or int
            Channel1Ratio for CH1 and Channel2Ratio for CH2.
            Ratio type for CH1:

                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2

            Ratio type for CH2:

                * 0 : none
                * 1 : Aux In 3
                * 2 : Aux In 4
        """
        _validate_enum(channel, Channel)
        _validate_enum(display, Channel1Display if channel == 1 else Channel2Display)
        _validate_enum(ratio, Channel1Ratio if channel == 1 else Channel2Ratio)
        if (channel in [1, 2]) and (display in range(5)) and (ratio in range(3)):
            self._write(f"DDEF {int(channel)}, {int(display)}, {int(ratio)}")
        else:
            raise ValueError(
                f"Invalid channel, display, or ratio: {channel}, {display}, or {ratio}"
                + ". Channel must be 1 (Ch1) or 2 (Ch2); display must be an integer in"
                + " range 0 - 4; and ratio must be an integer in the range 0 - 2."
            )

    def get_display(self, channel: Channel | int) -> tuple[int, int]:
        """Get a channel display configuration.

        Parameters
        ----------
        channel : Channel or int
            Channel:

                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        display : {0, 1, 2, 3, 4}
            Display parameter for CH1:

                * 0 : X
                * 1 : R
                * 2 : X Noise
                * 3 : Aux In 1
                * 4 : Aux In 2;

            Display parameter for CH2:

                * 0 : Y
                * 1 : Phase
                * 2 : Y Noise
                * 3 : Aux In 3
                * 4 : Aux In 4

        ratio : {0, 1, 2}
            Channel1Ratio for CH1 and Channel2Ratio for CH2.
            Ratio type for CH1:

                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2

            Ratio type for CH2:

                * 0 : none
                * 1 : Aux In 2
                * 2 : Aux In 4
        """
        _validate_enum(channel, Channel)
        if channel in [1, 2]:
            display, ratio = self._query(f"DDEF? {int(channel)}").split(",")
            return int(display), int(ratio)
        else:
            raise ValueError(f"Invalid channel: {channel}. Must be 0 (Ch1) or 1 (Ch2).")

    def set_front_output(
        self,
        channel: Channel | int,
        output: FrontPanelOutputSource | int = 0,
    ) -> None:
        """Set front panel output sources.

        Parameters
        ----------
        channel : Channel or int
            Channel:

                * 1 : CH1
                * 2 : CH2

        output : FrontPanelOutputSource or int
            Output quantity for CH1:

                * 0 : CH1 display
                * 1 : X

            Output quantity for CH2:

                * 0 : CH2 display
                * 1 : Y
        """
        _validate_enum(channel, Channel)
        _validate_enum(output, FrontPanelOutputSource)
        if (channel in [1, 2]) and (output in [0, 1]):
            self._write(f"FPOP {int(channel)}, {int(output)}")
        else:
            raise ValueError(
                f"Invalid channel or output: {channel} or {output}. Channel must be 0 "
                + "(Ch1) or 1 (Ch2); and output must be 0 or 1."
            )

    def get_front_output(self, channel: Channel | int) -> int:
        """Get front panel output sources.

        Parameters
        ----------
        channel : Channel or int
            Channel:

                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        output : {0, 1}
            Output quantity for CH1:

                * 0 : CH1 display
                * 1 : X

            Output quantity for CH2:

                * 0 : CH2 display
                * 1 : Y
        """
        _validate_enum(channel, Channel)
        if channel in [1, 2]:
            return int(self._query(f"FPOP? {int(channel)}"))
        else:
            raise ValueError(f"Invalid channel: {channel}. Must be 0 (Ch1) or 1 (Ch2).")

    def set_output_offset_expand(
        self,
        parameter: OutputParameter | int,
        offset: float,
        expand: OutputExpansion | int,
    ) -> None:
        """Set the output offsets and expands.

        Setting an offset to zero turns the offset off.

        Parameters
        ----------
        parameter : OutputParameter or int
            Measurement parameter:

                * 1 : X
                * 2 : Y
                * 3 : R

        offset : float
            Offset in %, -105.00 =< offset =< 105.00.
        expand : OutputExpansion or int
            Expansion factor; OutputExpansion.x1 has code 0:

                * 0 : 1 (no expansion)
                * 1 : 10
                * 2 : 100
        """
        _validate_enum(parameter, OutputParameter)
        _validate_enum(expand, OutputExpansion)
        if (
            (parameter in [1, 2, 3])
            and (offset >= -105)
            and (offset <= 105)
            and (expand in range(3))
        ):
            self._write(f"OEXP {int(parameter)}, {offset}, {int(expand)}")
        else:
            raise ValueError(
                f"Invalid parameter, offset, or expand: {parameter}, {offset}, or "
                + f"{expand}. Parameter must be 1 (X), 2 (Y), or 3 (R); offset must "
                + "be in the range -105 - 105 percent; and expand must be 0 (1), 1 "
                + "(10), or 2 (100)."
            )

    def get_output_offset_expand(
        self, parameter: OutputParameter | int
    ) -> tuple[float, int]:
        """Get the output offsets and expands.

        Parameters
        ----------
        parameter : OutputParameter or int
            Measurement parameter:

                * 1 : X
                * 2 : Y
                * 3 : R

        Returns
        -------
        offset : float
            Offset in %, -105.00 =< offset =< 105.00.
        expand : {0, 1, 2}
            Expansion factor; OutputExpansion.x1 has code 0:

                * 0 : 1 (no expansion)
                * 1 : 10
                * 2 : 100
        """
        _validate_enum(parameter, OutputParameter)
        if parameter in range(1, 4):
            offset, expand = self._query(f"OEXP? {int(parameter)}").split(",")
            return float(offset), int(expand)
        else:
            raise ValueError(
                f"Invalid paramter: {parameter}. Must be 1 (X), 2 (Y), or 3 (R)."
            )

    def auto_offset(self, parameter: OutputParameter | int) -> None:
        """Set parameter offset to zero.

        Parameters
        ----------
        parameter : OutputParameter or int
            Measurement parameter:

                * 1 : X
                * 2 : Y
                * 3 : R
        """
        _validate_enum(parameter, OutputParameter)
        if parameter in range(1, 4):
            self._write(f"AOFF {int(parameter)}")
        else:
            raise ValueError(
                f"Invalid paramter: {parameter}. Must be 1 (X), 2 (Y), or 3 (R)."
            )

    # --- Aux input and output commands ---

    def get_aux_in(self, aux_in: AuxiliaryChannel | int) -> float:
        """Get voltage of auxiliary input.

        The resolution is 1/3 mV.

        Parameter
        ---------
        aux_in : AuxiliaryChannel or int
            Auxiliary input (1, 2, 3, or 4).

        Returns
        -------
        voltage : float
            Auxiliary input voltage.
        """
        _validate_enum(aux_in, AuxiliaryChannel)
        if aux_in in [1, 2, 3, 4]:
            return float(self._query(f"OAUX? {int(aux_in)}"))
        else:
            raise ValueError(
                f"Invalid auxilliary input: {aux_in}. Must be an integer in range "
                + "1 - 4."
            )

    def set_aux_out(self, aux_out: AuxiliaryChannel | int, voltage: float) -> None:
        """Set voltage of auxiliary output.

        Parameters
        ----------
        aux_out : AuxiliaryChannel or int
            Auxiliary output (1, 2, 3, or 4).
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        _validate_enum(aux_out, AuxiliaryChannel)
        if (aux_out in [1, 2, 3, 4]) and (voltage >= -10.5) and (voltage <= 10.5):
            self._write(f"AUXV {int(aux_out)}, {voltage}")
        else:
            raise ValueError(
                f"Invalid auxilliary output or voltage: {aux_out} or {voltage}. Aux "
                + "out must be an integer in range 1 - 4, and voltage must be in "
                + "range -10.5 - 10.5 volts."
            )

    def get_aux_out(self, aux_out: AuxiliaryChannel | int) -> float:
        """Get voltage of auxiliary output.

        Parameters
        ----------
        aux_out : AuxiliaryChannel or int
            Auxiliary output (1, 2, 3, or 4).

        Returns
        -------
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        _validate_enum(aux_out, AuxiliaryChannel)
        if aux_out in [1, 2, 3, 4]:
            return float(self._query(f"AUXV? {int(aux_out)}"))
        else:
            raise ValueError(
                f"Invalid auxilliary output: {aux_out}. Must be an integer in range "
                + "1 - 4."
            )

    # --- Setup commands ---

    @property
    def key_click_state(self) -> int:
        """Get key click state.

        Returns an integer code; use SwitchState(code) for its named setting.

        Returns
        -------
        state : {0, 1}
            Key click state:

                * 0 : Off
                * 1 : On
        """
        return int(self._query("KCLK?"))

    @key_click_state.setter
    def key_click_state(self, state: SwitchState | int) -> None:
        """Set key click state.

        Parameters
        ----------
        state : SwitchState or int
            Key click state:

                * 0 : Off
                * 1 : On
        """
        _validate_enum(state, SwitchState)
        if state in [0, 1]:
            self._write(f"KCLK {int(state)}")
        else:
            raise ValueError(
                f"Invalid key click state: {state}. Must be 0 (off) or 1 (on)."
            )

    @property
    def alarm_status(self) -> int:
        """Get the alarm status.

        Returns an integer code; use SwitchState(code) for its named setting.

        The 'alarm' refers to all sounds emitted by the instrument.

        Returns
        -------
        status : {0, 1}
            Alarm status:

                * 0 : Off
                * 1 : On
        """
        return int(self._query("ALRM?"))

    @alarm_status.setter
    def alarm_status(self, status: SwitchState | int) -> None:
        """Set the alarm status.

        The 'alarm' refers to all sounds emitted by the instrument.

        Parameters
        ----------
        status : SwitchState or int
            Alarm status:

                * 0 : Off
                * 1 : On
        """
        _validate_enum(status, SwitchState)
        if status in [0, 1]:
            self._write(f"ALRM {int(status)}")
        else:
            raise ValueError(
                f"Invalid alarm status: {status}. Must be 0 (off) or 1 (on)."
            )

    def save_setup(self, number: int) -> None:
        """Save the lock-in setup in a settings buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        _require_integer(number, "number")
        if number in range(1, 10):
            self._write(f"SSET {number}")
        else:
            raise ValueError(
                f"Invalid save buffer number: {number}. Must be an integer in range "
                + "1 - 9."
            )

    def recall_setup(self, number: int) -> None:
        """Recall lock-in setup from setting buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        _require_integer(number, "number")
        if number in range(1, 10):
            self._write(f"RSET {number}")
        else:
            raise ValueError(
                f"Invalid save buffer number: {number}. Must be an integer in range "
                + "1 - 9."
            )

    # --- Auto functions ---

    def auto_gain(self) -> None:
        """Automatically set the gain.

        Does nothing if the time constant is greater than 1 second.
        """
        self._write("AGAN")

    def auto_reserve(self) -> None:
        """Automatically set reserve."""
        self._write("ARSV")

    def auto_phase(self) -> None:
        """Automatically set phase."""
        self._write("APHS")

    # --- Data storage commands ---

    @property
    def sample_rate(self) -> int:
        """Get the data sample rate.

        Returns an integer code; use SampleRate(code) for its named setting.

        Returns
        ---------
        rate : {0 - 14} or float or int or "Trigger"
            Sample rate in Hz:

                * 0 : 62.5e-3
                * 1 : 125e-3
                * 2 : 250e-3
                * 3 : 500e-3
                * 4 : 1
                * 5 : 2
                * 6 : 4
                * 7 : 8
                * 8 : 16
                * 9 : 32
                * 10 : 64
                * 11 : 128
                * 12 : 256
                * 13 : 512
                * 14 : Trigger
        """
        return int(self._query("SRAT?"))

    @sample_rate.setter
    def sample_rate(self, rate: SampleRate | int) -> None:
        """Set the data sample rate.

        Paramters
        ---------
        rate : SampleRate or int
            Sample rate in Hz:

                * 0 : 62.5e-3
                * 1 : 125e-3
                * 2 : 250e-3
                * 3 : 500e-3
                * 4 : 1
                * 5 : 2
                * 6 : 4
                * 7 : 8
                * 8 : 16
                * 9 : 32
                * 10 : 64
                * 11 : 128
                * 12 : 256
                * 13 : 512
                * 14 : Trigger
        """
        _validate_enum(rate, SampleRate)
        if rate in range(15):
            self._write(f"SRAT {int(rate)}")
        else:
            raise ValueError(
                f"Invalid sample rate: {rate}. Must be an integer in range 0 - 14."
            )

    @property
    def end_of_buffer_mode(self) -> int:
        """Get the end of buffer mode.

        Returns an integer code; use EndOfBufferMode(code) for its named setting.

        Returns
        ----------
        mode : {0, 1} or str
            End of buffer mode:

                * 0 : 1 Shot
                * 1 : Loop
        """
        return int(self._query("SEND?"))

    @end_of_buffer_mode.setter
    def end_of_buffer_mode(self, mode: EndOfBufferMode | int) -> None:
        """Set the end of buffer mode.

        If Loop mode is used, make sure to pause data storage before reading the
        data to avoid confusion about which point is the most recent.

        Parameters
        ----------
        mode : EndOfBufferMode or int
            End of buffer mode:

                * 0 : 1 Shot
                * 1 : Loop
        """
        _validate_enum(mode, EndOfBufferMode)
        if mode in [0, 1]:
            self._write(f"SEND {int(mode)}")
        else:
            raise ValueError(
                f"Invalid end of buffer mode: {mode}. Must be 0 (1 shot) or 1 (loop)."
            )

    def trigger(self) -> None:
        """Send software trigger, tracking a trigger-started FAST stream."""
        starts_fast = False
        if not self._fast_running:
            starts_fast = bool(self.trigger_start_mode and self.data_transfer_mode)
        if starts_fast:
            self._raw_write("TRIG")
            self._fast_running = True
        else:
            self._write("TRIG")

    @property
    def trigger_start_mode(self) -> int:
        """Get the trigger start mode.

        Returns an integer code; use TriggerStartMode(code) for its named setting.

        Returns
        -------
        mode : {0, 1} or str
            Trigger start mode:

                * 0 : Off
                * 1 : Start scan
        """
        return int(self._query("TSTR?"))

    @trigger_start_mode.setter
    def trigger_start_mode(self, mode: TriggerStartMode | int) -> None:
        """Set the trigger start mode.

        Parameters
        ----------
        mode : TriggerStartMode or int
            Trigger start mode:

                * 0 : Off
                * 1 : Start scan
        """
        _validate_enum(mode, TriggerStartMode)
        if mode in [0, 1]:
            self._write(f"TSTR {int(mode)}")
        else:
            raise ValueError(
                f"Invalid trigger start mode: {mode}. Must be 0 (off) or 1 "
                + "(start scan)."
            )

    def start(self) -> None:
        """Start or resume data storage.

        Ignored if storage already in progress.

        After turning on fast data transfer, this function starts the scan after a
        delay of 0.5 sec.
        """
        if self._fast_running:
            return
        if self.data_transfer_mode == 0:
            # fast data transfer off
            self._write("STRT")
        else:
            # fast data transfer mode active
            self._raw_write("STRD")
            self._fast_running = True

    def pause(self) -> None:
        """Pause data storage.

        Ignored if storage is already paused or reset. Pending FAST output is
        discarded with VISA device clear before text queries are allowed again.
        """
        if self._fast_running:
            self._raw_write("PAUS")
            self._discard_fast_data()
            self._fast_running = False
            self.check_errors(operation="PAUS")
            self.check_measurement_status(operation="PAUS")
        else:
            self._write("PAUS")

    def reset_data_buffers(self) -> None:
        """Reset data buffers.

        This command will erase the data buffer.
        """
        if self._fast_running:
            self._raw_write("REST")
            self._discard_fast_data()
            self._fast_running = False
            self.check_errors(operation="REST")
            self.check_measurement_status(operation="REST")
        else:
            self._write("REST")

    # --- Data transfer commands ---

    def measure(self, parameter: MeasurementParameter | int) -> float:
        """Read the value of X, Y, R, or phase.

        Parameters
        ----------
        parameter : MeasurementParameter or int
            Measured parameter; only X, Y, R, and PHASE are accepted:

                * 1 : X
                * 2 : Y
                * 3 : R
                * 4 : Phase

        Returns
        -------
        value : float
            Value of measured parameter in volts or degrees.
        """
        _validate_enum(parameter, MeasurementParameter)
        if parameter in range(1, 5):
            value = float(self._query(f"OUTP? {int(parameter)}"))
            self.check_measurement_status(operation=f"OUTP? {int(parameter)}")
            return value
        else:
            raise ValueError(
                f"Invalid parameter: {parameter}. Must be 1 (X), 2 (Y), 3 (R), or 4 "
                + "(phase)."
            )

    def read_display(self, channel: Channel | int) -> float:
        """Read the value of a channel display.

        Parameters
        ----------
        channel : Channel or int
            Channel display to read:

                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        value : float
            Displayed value in display units.
        """
        _validate_enum(channel, Channel)
        if channel in [1, 2]:
            value = float(self._query(f"OUTR? {int(channel)}"))
            self.check_measurement_status(operation=f"OUTR? {int(channel)}")
            return value
        else:
            raise ValueError(f"Invalid channel: {channel}. Must be 0 (Ch1) or 1 (Ch2).")

    def measure_multiple(
        self,
        parameters: Sequence[MeasurementParameter | int],
    ) -> Iterator[float]:
        """Read multiple (2-6) parameter values simultaneously.

        The values of X and Y are recorded at a single instant.
        The values of R and phase are also recorded at a single
        instant. Thus reading X,Y OR R,phase yields a coherent snapshot
        of the output signal. If X,Y,R and phase are all read, then the
        values of X,Y are recorded approximately 10µs apart from
        R,phase. Thus, the values of X and Y may not yield the exact
        values of R and phase from a single SNAP? query.

        The values of the Aux Inputs may have an uncertainty of up to
        32µs. The frequency is computed only every other period or 40 ms,
        whichever is longer.

        Parameters
        ----------
        parameters : Sequence[MeasurementParameter | int]
            Parameters to measure:

                * 1 : X
                * 2 : Y
                * 3 : R
                * 4 : Phase
                * 5 : Aux In 1
                * 6 : Aux In 2
                * 7 : Aux In 3
                * 8 : Aux In 4
                * 9 : Ref Frequency
                * 10 : CH1 display
                * 11 : CH2 display

        Returns
        -------
        values : iterator of float
            Values of measured parameters.
        """
        for parameter in parameters:
            _validate_enum(parameter, MeasurementParameter)
        if all(p in range(1, 12) for p in parameters) and (
            len(parameters) in range(2, 7)
        ):
            parameter_text = ",".join([str(int(i)) for i in parameters])
            values = self._query(f"SNAP? {parameter_text}").split(",")
            self.check_measurement_status(operation=f"SNAP? {parameter_text}")
            return (float(i) for i in values)
        else:
            raise ValueError(
                f"Invalid parameter list: {parameters}. All paramters must be integers"
                + " in the range 1 - 11 and the list length must be in the range 2 - 6"
                + "."
            )

    @property
    def buffer_size(self) -> int:
        """Get the number of points stored in the buffer.

        Returns
        -------
        N : int
            Number of points in the buffer.
        """
        return int(self._query("SPTS?"))

    @contextmanager
    def _buffer_read(
        self, channel: Channel | int, start_bin: int, bins: int, resume: bool
    ) -> Iterator[None]:
        _validate_enum(channel, Channel)
        _require_integer(start_bin, "start_bin")
        _require_integer(bins, "bins")
        if (
            channel not in (1, 2)
            or start_bin < 0
            or bins < 1
            or start_bin + bins > 16383
        ):
            raise ValueError(
                "Invalid channel or buffer range (capacity is 16383 points)."
            )
        if not isinstance(resume, bool):
            raise ValueError("resume must be a bool.")
        if self._fast_running:
            raise RuntimeError("Stop fast transfer before issuing buffer queries.")
        loop = self.end_of_buffer_mode == EndOfBufferMode.LOOP
        if loop:
            self.pause()
        if start_bin + bins > self.buffer_size:
            raise ValueError("Requested range exceeds the stored buffer points.")
        yield
        self.check_measurement_status(operation="buffer read")
        # Deliberately do not resume after transfer/decoding failures.
        if loop and resume:
            self.start()

    def get_ascii_buffer_data(
        self, channel: Channel | int, start_bin: int, bins: int, *, resume: bool = False
    ) -> tuple[float, ...]:
        """Read exactly bins ASCII samples, starting at the zero-based start_bin.

        Channel must be 1 or 2; the requested range must exist in the buffer.
        Loop scans are paused and left paused. Pass resume=True to start them
        again after a successful read (even if already paused before this call).
        Errors leave loop scans paused.

        Parameters
        ----------
        channel : Channel or int
            Display buffer, 1 or 2.
        start_bin : int
            Zero-based index of the oldest requested point.
        bins : int
            Positive number of points; start_bin + bins must not exceed the
            acquired length or the 16383-point capacity.
        resume : bool, optional
            Restart a loop scan after success. Defaults to False.

        Returns
        -------
        tuple of float
            Buffer samples in the selected display's units.
        """
        with self._buffer_read(channel, start_bin, bins, resume):
            fields = self._query_ascii_values(
                f"TRCA? {int(channel)},{start_bin},{bins}"
            )
            fields = [field.strip() for field in fields]
            if fields and fields[-1] == "":
                fields.pop()
            if len(fields) != bins:
                raise OSError(
                    f"Incomplete ASCII response: expected {bins} points, received {len(fields)}."
                )
            try:
                result = tuple(float(field) for field in fields)
            except ValueError as exc:
                raise OSError("Invalid number in ASCII buffer response.") from exc
        return result

    def get_binary_buffer_data(
        self, channel: Channel | int, start_bin: int, bins: int, *, resume: bool = False
    ) -> tuple[float, ...]:
        """Read exactly bins little-endian IEEE float samples in display units.

        Range and pause/resume behavior match get_ascii_buffer_data(). Serial
        transfers require eight data bits; SRS recommends GPIB for binary data.
        """
        with self._buffer_read(channel, start_bin, bins, resume):
            if self.output_interface == OutputInterface.RS232:
                warnings.warn(
                    "SRS recommends not using binary transfers over serial interfaces.",
                    stacklevel=2,
                )
            raw = self._read_buffer_bytes(
                f"TRCB? {int(channel)},{start_bin},{bins}", 4 * bins
            )
            result = struct.unpack(f"<{bins}f", raw)
        return result

    def get_non_norm_buffer_data(
        self, channel: Channel | int, start_bin: int, bins: int, *, resume: bool = False
    ) -> tuple[float, ...]:
        """Read SR830 mantissa/exponent samples in display units.

        Range and pause/resume behavior match get_ascii_buffer_data(). Errors
        leave loop scans paused. Each sample occupies four binary bytes.
        """
        with self._buffer_read(channel, start_bin, bins, resume):
            if self.output_interface == OutputInterface.RS232:
                warnings.warn(
                    "SRS recommends not using binary transfers over serial interfaces.",
                    stacklevel=2,
                )
            raw = self._read_buffer_bytes(
                f"TRCL? {int(channel)},{start_bin},{bins}", 4 * bins
            )
            words = struct.unpack(f"<{2 * bins}h", raw)
            result = tuple(
                float(m * 2 ** (e - 124)) for m, e in zip(words[::2], words[1::2])
            )
        return result

    @property
    def data_transfer_mode(self) -> int:
        """Get the data transfer mode.

        Returns an integer code; use DataTransferMode(code) for its named setting.

        Returns
        -------
        mode : {0, 1, 2}
            Data transfer mode:

                * 0 : Off
                * 1 : On (DOS)
                * 2 : On (Windows)
        """
        return int(self._query("FAST?"))

    @data_transfer_mode.setter
    def data_transfer_mode(self, mode: DataTransferMode | int) -> None:
        """Set the data transfer mode.

        GPIB only.

        Parameters
        ----------
        mode : DataTransferMode or int
            Data transfer mode:

                * 0 : Off
                * 1 : On (DOS)
                * 2 : On (Windows)
        """
        _validate_enum(mode, DataTransferMode)
        if mode in range(3):
            if self._fast_running and mode != DataTransferMode.OFF:
                raise RuntimeError("Stop fast transfer before changing its mode.")
            if (
                mode != DataTransferMode.OFF
                and self.output_interface != OutputInterface.GPIB
            ):
                raise ValueError(
                    "Fast transfer requires the instrument GPIB output interface."
                )
            self._write(f"FAST {int(mode)}")
            if mode == DataTransferMode.OFF:
                if self._fast_running:
                    self._discard_fast_data()
                was_running = self._fast_running
                self._fast_running = False
                if was_running:
                    self.check_errors(operation="FAST 0")
                    self.check_measurement_status(operation="FAST 0")
        else:
            raise ValueError(
                f"Invalid data transfer mode: {mode}. Must be 0 (off), 1 (on [DOS]), "
                + "or 2 (on [Windows])."
            )

    # --- Interface commands ---

    def reset(self) -> None:
        """Reset the instrument to the default configuration."""
        if self._fast_running:
            self._raw_write("*RST")
            self._discard_fast_data()
            self._fast_running = False
            self.check_errors(operation="*RST")
            self.check_measurement_status(operation="*RST")
        else:
            self._write("*RST")

    @property
    def idn(self) -> str:
        """Get the device identification string.

        The string is in the format "Stanford_Research_Systems,SR830,s/n00111,ver1.000",
        where, for example, the serial number is 00111 and the firmware version is
        1.000.

        Returns
        -------
        idn : list
            List of identification strings consisting of manufacturer, model, serial
            number, and firmware version number in order.
        """
        return self._query("*IDN?")

    @property
    def local_mode(self) -> int:
        """Get the local/remote function.

        Returns an integer code; use LocalMode(code) for its named setting.

        Returns
        -------
        local : {0, 1, 2}
            Local/remote function:

                * 0 : LOCAL
                * 1 : REMOTE
                * 2 : LOCAL LOCKOUT
        """
        return int(self._query("LOCL?"))

    @local_mode.setter
    def local_mode(self, mode: LocalMode | int) -> None:
        """Set the local/remote function.

        Parameters
        ----------
        mode : LocalMode or int
            Local/remote function:

                * 0 : LOCAL
                * 1 : REMOTE
                * 2 : LOCAL LOCKOUT
        """
        _validate_enum(mode, LocalMode)
        if mode in range(3):
            self._write(f"LOCL {int(mode)}")
        else:
            raise ValueError(
                f"Invalid local mode: {mode}. Must be 0 (local), 1 (remote), or 2 "
                + "(local lockout)."
            )

    @property
    def gpib_override_remote(self) -> int:
        """Get the GPIB override remote condition.

        Returns an integer code; use GpibOverrideRemote(code) for its named setting.

        Under normal operation every GPIB command puts the instrument in the remote
        state with the front panel deactivated.

        Returns
        -------
        condition : int
            GPIB override remote condition:

                * 0 : No
                * 1 : Yes
        """
        return int(self._query("OVRM?"))

    @gpib_override_remote.setter
    def gpib_override_remote(self, condition: GpibOverrideRemote | int) -> None:
        """Set the GPIB override remote condition.

        Under normal operation every GPIB command puts the instrument in the remote
        state with the front panel deactivated.

        Parameters
        ----------
        condition : GpibOverrideRemote or int
            GPIB override remote condition:

                * 0 : No
                * 1 : Yes
        """
        _validate_enum(condition, GpibOverrideRemote)
        if condition in [0, 1]:
            self._write(f"OVRM {int(condition)}")
        else:
            raise ValueError(
                f"Invalid GPIB override remote condition: {condition}. Must be 0 (no) "
                + "or 1 (yes)."
            )

    # --- Status reporting commands ---

    def clear_status_registers(self) -> None:
        """Clear all status registers."""
        self._write("*CLS")

    def set_enable_register(
        self,
        register: StatusRegister | str,
        value: StandardEventFlag
        | SerialPollFlag
        | ErrorFlag
        | LiaStatusFlag
        | SwitchState
        | int,
        decimal: bool = True,
        bit: StandardEventBit
        | SerialPollBit
        | ErrorBit
        | LiaStatusBit
        | int
        | None = None,
    ) -> None:
        """Set an enable register.

        Parameters
        ----------
        register : StatusRegister or str
            Enable register to set.
        value : StandardEventFlag | SerialPollFlag | ErrorFlag | LiaStatusFlag | SwitchState or int
            Whole-byte mask (0-255) when decimal=True; use the flag type
            matching the register and combine flags with |. When decimal=False,
            use SwitchState or 0/1 for the bit specified by bit.
        decimal : bool, optional
            True writes a whole-byte mask; False writes a single bit state.
        bit : StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit or int, optional
            Bit position, not a mask. Use the bit enum matching the register
            or an integer from 0 to 7; required when decimal=False.
        """
        _validate_register_bit(register, bit)
        _validate_register_value(register, value, decimal)
        command = _ENABLE_REGISTER_COMMANDS[register]
        if decimal:
            arguments = str(int(value))
        else:
            if bit is None:
                raise ValueError("bit is required when decimal=False.")
            arguments = f"{int(bit)},{int(value)}"
        self._write(f"{command} {arguments}")

    def get_enable_register(
        self,
        register: StatusRegister | str,
        bit: StandardEventBit
        | SerialPollBit
        | ErrorBit
        | LiaStatusBit
        | int
        | None = None,
    ) -> int:
        """Get the standard event enable register value.

        Parameters
        ----------
        register : StatusRegister or str
            Enable register to get.
        bit : StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit or int, optional
            Bit position, not a mask; the enum must match the register.
            If None, query the entire byte (an integer mask).

        Returns
        -------
        value : int
            Register value.
        """
        _validate_register_bit(register, bit)
        command = f"{_ENABLE_REGISTER_COMMANDS[register]}?"
        if bit is not None:
            command += f" {int(bit)}"
        return int(self._query(command))

    def get_status_byte(
        self,
        status_byte: StatusRegister | str,
        bit: StandardEventBit
        | SerialPollBit
        | ErrorBit
        | LiaStatusBit
        | int
        | None = None,
    ) -> int:
        """Get a status byte.

        This raw diagnostic does not perform automatic fault checks or read any
        other register. Event-register reads clear the queried latched bits.

        Parameters
        ----------
        status_byte : StatusRegister or str
            Status byte to get.
        bit : StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit or int, optional
            Bit position, not a mask; the enum must match the register.
            If None, query the entire byte (an integer mask).

        Returns
        -------
        value : int
            Status byte value.
        """
        _validate_register_bit(status_byte, bit)
        command = _STATUS_REGISTER_COMMANDS[status_byte]
        if bit is not None:
            command += f" {int(bit)}"
        return int(self._raw_query(command))

    @property
    def power_on_status_clear_bit(self) -> int:
        """Get the power-on status clear bit.

        Returns an integer code; use SwitchState(code) for its named setting.

        Returns
        -------
        value : int
            Power-on status clear bit value.
        """
        return int(self._query("*PSC?"))

    @power_on_status_clear_bit.setter
    def power_on_status_clear_bit(self, value: SwitchState | int) -> None:
        """Set the power-on status clear bit.

        Parameters
        ----------
        value : SwitchState or int
            Value of power-on status clear bit. Values:

                * 0 : Cleared, status enable registers maintain values at power down.
                * 1 : Set, all status and enable registers are cleared on power up.
        """
        _validate_enum(value, SwitchState)
        if value in [0, 1]:
            self._write(f"*PSC {int(value)}")
        else:
            raise ValueError(
                f"Invalid power on status clear bit: {value}. Must be 0 (cleared) or 1"
                + " (set)."
            )

    def serial_poll(self) -> int:
        """Perform a native VISA status-byte poll, acknowledging GPIB SRQ.

        Unlike get_status_byte(), this sends no *STB? query and can observe a
        busy instrument. Unsupported serial/socket backends raise NotImplementedError.
        """
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        try:
            return int(self._instr.read_stb())
        except NotImplementedError as exc:
            raise NotImplementedError(
                "This VISA resource does not support native status polling."
            ) from exc
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code in (
                pyvisa.constants.StatusCode.error_nonsupported_operation,
                pyvisa.constants.StatusCode.error_nonimplemented_operation,
            ):
                raise NotImplementedError(
                    "This VISA resource does not support native status polling."
                ) from exc
            raise

    @contextmanager
    def _io_timeout(self, seconds: float) -> Iterator[None]:
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        resource = self._instr
        previous = resource.timeout
        try:
            resource.timeout = max(1, math.ceil(seconds * 1000))
            yield
        finally:
            resource.timeout = previous

    def wait_until_ready(
        self, timeout: float = 10.0, *, poll_interval: float = 0.01
    ) -> None:
        """Wait for command completion within timeout seconds.

        Native polling is preferred. Unsupported resources use a queued *STB?
        query as a completion barrier, bounded by the remaining VISA timeout.
        This does not imply that the analog filter has settled.

        Parameters
        ----------
        timeout : float, optional
            Positive total command-completion budget in seconds.
        poll_interval : float, optional
            Positive delay between native polls in seconds.

        Raises
        ------
        TimeoutError
            Command completion was not observed within the budget.
        """
        self._validate_wait(timeout, poll_interval)
        deadline = time.monotonic() + timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "Timed out waiting for SR830 command completion."
                    )
                with self._io_timeout(remaining):
                    try:
                        ready = bool(
                            self.serial_poll() & SerialPollFlag.NO_COMMAND_IN_PROGRESS
                        )
                    except NotImplementedError:
                        self.get_status_byte(StatusRegister.SERIAL_POLL)
                        return
                if ready:
                    return
                time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                raise TimeoutError(
                    "Timed out waiting for SR830 command completion."
                ) from exc
            raise

    @staticmethod
    def _validate_wait(timeout: float, interval: float) -> None:
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not math.isfinite(interval)
            or interval <= 0
        ):
            raise ValueError(
                "Timeout and polling interval must be finite and positive."
            )

    def wait_for_settling(
        self, timeout: float = 60.0, *, time_constants: float = 10.0
    ) -> None:
        """Wait for completion and then time_constants times the filter time constant.

        This is a timing estimate, not a measurement-stability test. timeout is
        a total budget in seconds; insufficient budgets raise TimeoutError.
        External locking and synchronous-filter transients are not included.

        Parameters
        ----------
        timeout : float, optional
            Positive total budget for completion, querying, and settling, in seconds.
        time_constants : float, optional
            Positive multiple of the selected low-pass time constant to wait.
        """
        self._validate_wait(timeout, time_constants)
        started = time.monotonic()
        self.wait_until_ready(timeout)
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Settling timeout expired.")
        try:
            with self._io_timeout(remaining):
                delay = time_constants * _time_constant_seconds(self.time_constant)
        except pyvisa.errors.VisaIOError as exc:
            if exc.error_code == pyvisa.constants.StatusCode.error_timeout:
                raise TimeoutError(
                    "Timed out querying the filter time constant."
                ) from exc
            raise
        if delay > timeout - (time.monotonic() - started):
            raise TimeoutError("Settling requires more time than the supplied timeout.")
        time.sleep(delay)

    def read_fast_data(
        self, samples: int, *, timeout: float = 10.0
    ) -> tuple[tuple[int, int], ...]:
        """Read streamed GPIB X/Y pairs as signed 16-bit instrument counts.

        Call data_transfer_mode=WINDOWS or DOS, then start(), before reading.
        Counts include output offsets/expands; +/-30000 corresponds to the
        selected full scale before expansion. This method sends no text query.
        A failed read attempts to stop acquisition and discard pending output;
        call pause() after a successful final read. Counts are provisional until
        stopping the stream checks command/device and measurement faults.

        Parameters
        ----------
        samples : int
            Positive number of X/Y pairs to read.
        timeout : float, optional
            Positive VISA read timeout in seconds.

        Returns
        -------
        tuple of tuple of int
            Ordered (X, Y) count pairs, each component in -32768 to 32767.
        """
        _require_integer(samples, "samples")
        if samples < 1:
            raise ValueError("samples must be positive.")
        self._validate_wait(timeout, 1.0)
        if not self._fast_running:
            raise RuntimeError("Start a fast transfer before reading its stream.")
        try:
            with self._io_timeout(timeout):
                raw = self._read_fast_bytes(samples * 4)
            if len(raw) != samples * 4:
                raise OSError("Incomplete fast-transfer response.")
            return tuple(struct.iter_unpack("<hh", raw))
        except BaseException as exc:
            try:
                self.pause()
            except InstrumentError as fault:
                raise fault from exc
            except Exception:
                pass
            if (
                isinstance(exc, pyvisa.errors.VisaIOError)
                and exc.error_code == pyvisa.constants.StatusCode.error_timeout
            ):
                raise TimeoutError("Timed out reading fast-transfer data.") from exc
            raise

    def _discard_fast_data(self) -> None:
        """Clear pending GPIB stream bytes before returning to text I/O.

        VISA device clear discards unread output; acquisition has already stopped.
        If clearing fails, keep the stream guard active until cleanup succeeds.
        """
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        self._instr.clear()

    def _read_fast_bytes(self, size: int) -> bytes:
        # Reuse binary framing cleanup without sending any command.
        if self._instr is None:
            raise RuntimeError(_NOT_CONNECTED_MESSAGE)
        resource = self._instr
        termination = resource.read_termination
        serial_end = (
            resource.end_input if isinstance(resource, SerialInstrument) else None
        )
        try:
            resource.read_termination = None
            if isinstance(resource, SerialInstrument):
                resource.end_input = SerialTermination.none
            return resource.read_bytes(size, break_on_termchar=False)
        finally:
            try:
                if isinstance(resource, SerialInstrument) and serial_end is not None:
                    resource.end_input = serial_end
            finally:
                resource.read_termination = termination
