"""Stateful SR830 simulation sharing the hardware driver's public interface.

Protocol reference: https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf.
Signal amplitude is RMS in V (voltage mode) or A (current mode), with input
phase in degrees. Filter settling and acquisition follow elapsed monotonic time.
"""

from __future__ import annotations

import cmath
import copy
import math
import struct
import time
from collections import deque
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any

import pyvisa
from pyvisa.constants import InterfaceType, StatusCode

from sr830 import SR830
from sr830._connection import connection_kwargs, resolve_output_interface
from sr830.settings import (
    _ENABLE_REGISTER_COMMANDS,
    _STATUS_REGISTER_COMMANDS,
    AuxiliaryChannel,
    Channel,
    Channel1Display,
    Channel1Ratio,
    Channel2Display,
    Channel2Ratio,
    DataTransferMode,
    EndOfBufferMode,
    ErrorFlag,
    FrontPanelOutputSource,
    GpibOverrideRemote,
    InputConfiguration,
    InputCoupling,
    InputShieldGrounding,
    LiaStatusFlag,
    LineNotchFilter,
    LocalMode,
    LowPassFilterSlope,
    MeasurementParameter,
    OutputExpansion,
    OutputInterface,
    ReferenceSource,
    ReferenceTrigger,
    ReserveMode,
    SampleRate,
    Sensitivity,
    SerialPollFlag,
    StandardEventFlag,
    StatusRegister,
    SwitchState,
    SynchronousFilter,
    TimeConstant,
    TriggerStartMode,
    _full_scale,
    _time_constant_seconds,
    _validate_enum,
    _validate_register_value,
)


class VirtualSR830(SR830):
    """SR830 simulator using the hardware interface and elapsed monotonic time.

    Public I/O requires connect(), just as on hardware. Input changes settle
    through the selected low-pass filters; timed acquisition needs no background
    thread or explicit stepping. Auto functions complete immediately.

    Inherited instrument properties issue command strings through the overridden
    raw I/O hooks. Those hooks interpret commands using this instance's private
    settings, registers, and buffers. Calculation helpers evolve the same state;
    there is no separate model object.

    Parameters
    ----------
    amplitude : float, optional
        Nonnegative RMS input amplitude in V or A, initially 0.001. Units follow
        the input configuration; changing that setting does not rescale amplitude.
    phase : float, optional
        Finite input phase in degrees, initially zero. Independent of the
        instrument's reference_phase_shift setting.
    external_frequency : float, optional
        External reference frequency in Hz, initially 1000.0. Used when the
        instrument's reference_source selects external mode. Must be finite
        and between 0.001 and 102000 Hz.
    external_locked : bool, optional
        External reference lock state, initially True. False latches reference
        unlock and produces a zero frequency reading in external mode.
    aux_inputs : sequence of float, optional
        Four auxiliary input voltages in channel order, initially
        (0.0, 0.0, 0.0, 0.0). Each must be finite and between -10.5 and 10.5 V.
        Values are copied into independent per-instance state.
    """

    def __init__(
        self,
        *,
        amplitude: float = 0.001,
        phase: float = 0.0,
        external_frequency: float = 1000.0,
        external_locked: bool = True,
        aux_inputs: Sequence[float] = (0.0, 0.0, 0.0, 0.0),
    ) -> None:
        """Create a disconnected driver and initialize its input model once.

        Validate amplitude and phase, then initialize instrument settings and
        acquisition/filter state. Configure external conditions through the same
        validated controls used for later updates. Input changes after construction
        preserve filter history.
        """
        super().__init__()
        self._connected = False
        if not math.isfinite(amplitude) or amplitude < 0:
            raise ValueError("Signal amplitude must be finite and nonnegative.")
        if not math.isfinite(phase):
            raise ValueError("Input phase must be finite.")
        self._amplitude = amplitude
        self._phase = phase
        self._external_frequency = 1000.0
        self._external_locked = True
        self._aux_inputs = [0.0] * 4
        self._setups: dict[
            int,
            tuple[
                dict[str, float | int],
                list[float],
                list[tuple[int, int]],
                list[tuple[float, int]],
                list[int],
            ],
        ] = {}
        self._registers = {
            name: 0 for name in ("standard_event", "serial_poll", "error", "lia_status")
        }
        self._enables = self._registers.copy()
        self._srq_acknowledged = False
        self._settings: dict[str, float | int] = {}
        self._reset_state()
        self._virtual_timeout = 10.0
        if len(aux_inputs) != 4:
            raise ValueError("aux_inputs must contain exactly four voltages.")
        self.set_external_reference(external_frequency, locked=external_locked)
        for channel, voltage in zip(AuxiliaryChannel, aux_inputs):
            self.set_aux_input(channel, voltage)

    def __enter__(self) -> VirtualSR830:
        """Return this driver; inherited context exit disconnects it."""
        return self

    # --- Connection lifecycle ---

    def connect(
        self,
        resource_name: str | None = None,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        output_interface: OutputInterface | int | None = None,
        **resource_kwargs: Any,
    ) -> None:
        """Connect the simulator without resolving or opening a VISA resource.

        Parameters
        ----------
        resource_name : str, optional
            Ignored. Accepted so shared application code can pass the same
            connection arguments to either driver. No VISA name parsing occurs.
        resource_manager : pyvisa.ResourceManager, optional
            Ignored and never accessed or closed. Accepted for compatibility
            with the hardware driver; the simulator needs no manager.
        output_interface : OutputInterface or int, optional
            Simulated RS232 (0) or GPIB (1). Defaults to GPIB when omitted or
            None. Select explicitly for interface-dependent protocol behavior.
        resource_kwargs : Any
            Hardware-compatible framing/opening options, validated for conflicts.
            timeout is in milliseconds; None represents an unlimited I/O budget.

        Notes
        -----
        Preserve settings and external inputs across reconnects. Enable status
        registers and check latched command/device faults. Connecting twice raises
        RuntimeError; an initialization fault leaves this driver disconnected.
        """
        if self._connected:
            raise RuntimeError("Instrument is already connected; disconnect first.")
        interface = resolve_output_interface(InterfaceType.gpib, output_interface)
        interface_type = (
            InterfaceType.asrl
            if interface == OutputInterface.RS232
            else InterfaceType.gpib
        )
        connection_kwargs(interface, resource_kwargs, interface_type=interface_type)
        timeout = resource_kwargs.get("timeout", 10000)
        self._virtual_timeout = math.inf if timeout is None else float(timeout) / 1000
        self._settings["OUTX"] = interface
        self._enables = {name: 255 for name in self._enables}
        self._io_desynchronized = False
        self._connected = True
        try:
            self.check_errors()
        except BaseException:
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Return to local mode and disconnect without resetting instrument state.

        Repeated calls are harmless. Catch up elapsed acquisition/filter time;
        always clear connection/stream tracking and select local mode even when
        updating state fails. No VISA resource or manager needs closing.
        """
        if self._connected:
            self._connected = False
            self._fast_running = False
            try:
                self._update_state()
            finally:
                self._settings["LOCL"] = LocalMode.LOCAL

    # --- External input and fault controls ---

    @property
    def amplitude(self) -> float:
        """Nonnegative RMS source amplitude in V or A, before offsets/expansion.

        The input configuration determines its units without rescaling its stored
        value. X/Y targets are amplitude*cos(phase) and amplitude*sin(phase),
        with phase converted to radians. Reading this property does no I/O.
        """
        return self._amplitude

    @amplitude.setter
    def amplitude(self, value: float) -> None:
        """Set a finite, nonnegative RMS source amplitude in V or A.

        Catch up the old input before changing it. Retain filter history so the
        new input settles using the configured time constant and slope.
        Invalid values raise ValueError before changing state.
        """
        if not math.isfinite(value) or value < 0:
            raise ValueError("Signal amplitude must be finite and nonnegative.")
        self._update_state()
        self._amplitude = value

    @property
    def phase(self) -> float:
        """Source phase in degrees, independent of reference_phase_shift.

        Any finite angle is allowed and is stored as supplied. The instrument's
        reference phase separately rotates the demodulated X/Y measurements.
        Reading this property does no I/O.
        """
        return self._phase

    @phase.setter
    def phase(self, value: float) -> None:
        """Set a finite source phase in degrees while retaining filter history.

        Catch up the old input before applying the new phase. Invalid values
        raise ValueError before changing state.
        """
        if not math.isfinite(value):
            raise ValueError("Input phase must be finite.")
        self._update_state()
        self._phase = value

    def set_aux_input(self, channel: AuxiliaryChannel | int, voltage: float) -> None:
        """Set an auxiliary input voltage independently of auxiliary outputs.

        Parameters
        ----------
        channel : AuxiliaryChannel or int
            Input channel 1 through 4.
        voltage : float
            Finite voltage in the range -10.5 to 10.5 V. Used by auxiliary reads,
            display selection, and ratio denominators.
        """
        _validate_enum(channel, AuxiliaryChannel)
        if (
            channel not in (1, 2, 3, 4)
            or not math.isfinite(voltage)
            or not -10.5 <= voltage <= 10.5
        ):
            raise ValueError("Invalid auxiliary input channel or voltage.")
        self._aux_inputs[int(channel) - 1] = voltage

    def set_external_reference(self, frequency: float, *, locked: bool = True) -> None:
        """Set external frequency/lock conditions independently of the source.

        Parameters
        ----------
        frequency : float
            Frequency from 0.001 through 102000 Hz.
        locked : bool, optional
            Default True. False latches reference unlock, makes external frequency
            read zero, and drives the demodulated target to zero in external mode.

        Notes
        -----
        Catch up the previous reference conditions first. Internal-reference mode
        continues to use its own configured oscillator frequency.
        """
        if not math.isfinite(frequency) or not 0.001 <= frequency <= 102000:
            raise ValueError("External frequency must be in range 0.001 to 102000 Hz.")
        if not isinstance(locked, bool):
            raise ValueError("locked must be a bool.")
        self._update_state()
        self._external_frequency = frequency
        self._external_locked = locked
        if not locked:
            self._registers["lia_status"] |= int(LiaStatusFlag.REFERENCE_UNLOCK)

    def inject_status(self, register: StatusRegister | str, value: int) -> None:
        """Latch fault/event flags for application error-handling tests.

        Parameters
        ----------
        register : StatusRegister or str
            Standard-event, device-error, or LIA-status register. Serial-poll status
            is computed and cannot be injected directly.
        value : int
            Register-compatible IntFlag mask or integer byte, combined with the
            existing bits using OR. Rearm the service-request latch.
        """
        _validate_register_value(register, value, True)
        if register not in ("standard_event", "error", "lia_status"):
            raise ValueError(
                "Inject an event register, not the computed serial-poll byte."
            )
        self._registers[register] |= int(value)
        self._srq_acknowledged = False

    # --- Instrument settings and status overrides ---

    @SR830.output_interface.setter
    def output_interface(self, interface: OutputInterface | int) -> None:
        """Select a valid response interface; reject changes during FAST."""
        _validate_enum(interface, OutputInterface)
        if self._fast_running:
            raise RuntimeError(
                "Stop fast transfer before changing the output interface."
            )
        if interface not in (0, 1):
            raise ValueError("Output interface must be 0 (RS232) or 1 (GPIB).")
        self._write(f"OUTX {int(interface)}")

    def serial_poll(self) -> int:
        """Read computed status without clearing events; acknowledge an SRQ."""
        self._check_connected()
        return self._status_byte(acknowledge=True)

    # --- Simulated I/O and command interpretation ---

    def _check_connected(self) -> None:
        """Raise RuntimeError if virtual I/O is attempted while disconnected."""
        if not self._connected:
            raise RuntimeError("Instrument is not connected.")

    def _raw_write(self, command: str) -> None:
        """Interpret a validated command using local state without checking faults.

        Require a connected, synchronized driver and catch up elapsed time before
        interpreting the command. The inherited _write wrapper owns subsequent
        register checks; FAST writes defer those checks.

        Update settings, register enables, setups, or acquisition state directly.
        Unsupported commands latch command error. An empty recalled setup or a
        frequency write in external mode latches execution error. Auto functions
        complete immediately; inherited public setters validate input ranges.
        """
        self._check_connected()
        self._check_synchronized()
        self._update_state()
        key, _, arguments = command.strip().partition(" ")
        args = [part.strip() for part in arguments.split(",")] if arguments else []
        if key == "*RST":
            self._reset_state()
        elif key == "*CLS":
            for register in self._registers:
                self._registers[register] = 0
            self._srq_acknowledged = False
        elif key in ("*ESE", "*SRE", "ERRE", "LIAE"):
            register = next(
                name
                for name, mnemonic in _ENABLE_REGISTER_COMMANDS.items()
                if mnemonic == key
            )
            if len(args) == 2:
                bit, state = map(int, args)
                self._enables[register] = (self._enables[register] & ~(1 << bit)) | (
                    state << bit
                )
            else:
                self._enables[register] = int(args[0])
            self._srq_acknowledged = False
        elif key == "DDEF":
            channel, display, ratio = map(int, args)
            self._displays[channel - 1] = (display, ratio)
        elif key == "FPOP":
            self._front_outputs[int(args[0]) - 1] = int(args[1])
        elif key == "OEXP":
            self._offsets[int(args[0]) - 1] = (float(args[1]), int(args[2]))
        elif key == "AUXV":
            self._aux_outputs[int(args[0]) - 1] = float(args[1])
        elif key in ("SSET", "RSET"):
            number = int(args[0])
            if key == "SSET":
                self._setups[number] = copy.deepcopy(
                    (
                        self._settings,
                        self._aux_outputs,
                        self._displays,
                        self._offsets,
                        self._front_outputs,
                    )
                )
            elif number not in self._setups:
                self._registers["standard_event"] |= int(
                    StandardEventFlag.EXECUTION_ERROR
                )
                return
            else:
                preserved = {
                    key: self._settings[key] for key in ("OUTX", "LOCL", "OVRM", "*PSC")
                }
                (
                    self._settings,
                    self._aux_outputs,
                    self._displays,
                    self._offsets,
                    self._front_outputs,
                ) = copy.deepcopy(self._setups[number])
                self._settings.update(preserved)
        elif key in ("STRT", "STRD"):
            if not self._running:
                self._running = self._scan_started = True
                self._last_sample = time.monotonic() + (0.5 if key == "STRD" else 0.0)
        elif key == "PAUS":
            self._running = False
        elif key == "REST":
            self._running = self._scan_started = False
            for buffer in self._buffers:
                buffer.clear()
            self._fast_queue.clear()
        elif key == "TRIG":
            self._registers["lia_status"] |= int(LiaStatusFlag.TRIGGER)
            if (
                self._settings["TSTR"] == TriggerStartMode.START_SCAN
                and not self._running
            ):
                self._running = self._scan_started = True
                self._last_sample = time.monotonic()
                return
            if self._running and self._settings["SRAT"] == SampleRate.TRIGGER:
                self._store_sample(time.monotonic())
        elif key in ("AGAN", "ARSV", "APHS", "AOFF"):
            value = self._filter_at(time.monotonic())
            if key == "APHS":
                self._settings["PHAS"] = float(self._settings["PHAS"]) + math.degrees(
                    cmath.phase(value)
                )
            elif (
                key == "AGAN"
                and _time_constant_seconds(int(self._settings["OFLT"])) <= 1
            ):
                amplitude = abs(value)
                code = next(
                    (
                        i
                        for i in Sensitivity
                        if _full_scale(int(i), int(self._settings["ISRC"])) >= amplitude
                    ),
                    Sensitivity.x1,
                )
                self._settings["SENS"] = code
            elif key == "ARSV":
                self._settings["RMOD"] = ReserveMode.LOW_NOISE
            elif key == "AOFF":
                parameter = int(args[0])
                raw = (value.real, value.imag, abs(value))[parameter - 1]
                _, expand = self._offsets[parameter - 1]
                self._offsets[parameter - 1] = (
                    max(-105.0, min(105.0, raw / self._full_scale() * 100)),
                    expand,
                )
        elif key in self._settings:
            if key == "FREQ" and self._settings["FMOD"] == ReferenceSource.EXTERNAL:
                self._registers["standard_event"] |= int(
                    StandardEventFlag.EXECUTION_ERROR
                )
                return
            value_number = (
                float(args[0]) if key in ("PHAS", "FREQ", "SLVL") else int(args[0])
            )
            self._settings[key] = value_number
            if key in ("OFLT", "ISRC", "SENS"):
                if key == "OFLT" and value_number != TimeConstant.us_10:
                    self._registers["lia_status"] |= int(
                        LiaStatusFlag.TIME_CONSTANT_CHANGED
                    )
            if key == "HARM":
                frequency = self._reference_frequency()
                if frequency > 0:
                    self._settings["HARM"] = min(
                        int(value_number), max(1, int(102000 / frequency))
                    )
            if (
                key == "SENS"
                and value_number >= Sensitivity.x20m
                and self._settings["ISRC"] == InputConfiguration.CURRENT_100_MOHM
            ):
                self._settings["ISRC"] = InputConfiguration.CURRENT_1_MOHM
            if key == "FAST" and not value_number:
                self._fast_queue.clear()
        else:
            self._registers["standard_event"] |= int(StandardEventFlag.COMMAND_ERROR)
            return

    def _raw_query(self, command: str) -> str:
        """Interpret a query and return an unframed response from local state.

        Require a connected, synchronized driver and reject text queries during
        FAST streaming. Unsupported queries latch an error and raise a VISA
        timeout, allowing the inherited checked wrapper to diagnose the fault.

        Return numeric settings, identity, comma-separated measurements, trace
        samples, or register bytes/bits. Event-register queries clear the selected
        latches; enable-register queries and *STB? leave events untouched.
        Numeric replies use _format_values() so enum names never enter the wire
        protocol, including on Python 3.10.
        """
        self._check_connected()
        if self._fast_running:
            raise RuntimeError("Stop fast transfer before issuing text queries.")
        self._check_synchronized()
        self._update_state()
        key, _, arguments = command.strip().partition(" ")
        key = key.rstrip("?")
        args = [part.strip() for part in arguments.split(",")] if arguments else []
        if key == "*IDN":
            return "Virtual_Stanford_Research_Systems,SR830,s/n00000,ver1.07"
        if key in ("*ESE", "*SRE", "ERRE", "LIAE", "*ESR", "*STB", "ERRS", "LIAS"):
            commands = (
                _ENABLE_REGISTER_COMMANDS
                if key in ("*ESE", "*SRE", "ERRE", "LIAE")
                else _STATUS_REGISTER_COMMANDS
            )
            register = next(
                name
                for name, mnemonic in commands.items()
                if mnemonic.rstrip("?") == key
            )
            is_enable = key in ("*ESE", "*SRE", "ERRE", "LIAE")
            byte = (
                self._enables[register]
                if is_enable
                else (
                    self._status_byte() if key == "*STB" else self._registers[register]
                )
            )
            result = ((byte >> int(args[0])) & 1) if args else byte
            if not is_enable and key != "*STB":
                self._registers[register] &= ~(1 << int(args[0])) if args else 0
            return self._format_values(result)
        if key in ("DDEF", "FPOP", "OEXP", "OAUX", "AUXV"):
            index = int(args[0]) - 1
            if key == "DDEF":
                return self._format_values(*self._displays[index])
            if key == "FPOP":
                return self._format_values(self._front_outputs[index])
            if key == "OEXP":
                return self._format_values(*self._offsets[index])
            return self._format_values(
                (self._aux_inputs if key == "OAUX" else self._aux_outputs)[index]
            )
        if key == "SPTS":
            return self._format_values(len(self._buffers[0]))
        if key in ("TRCA", "TRCB", "TRCL"):
            channel, start, bins = map(int, args)
            return (
                self._format_values(
                    *list(self._buffers[channel - 1])[start : start + bins]
                )
                + ","
            )
        if key in ("OUTP", "OUTR", "SNAP"):
            value = self._filter_at(time.monotonic())

            def measurement(parameter: int) -> float:
                """Select one SNAP value from the shared filtered instant.

                Codes 1-4 select X/Y/R/phase, 5-8 auxiliary inputs, 9 reference
                frequency, and 10-11 channel displays. Components use V or A,
                phase uses degrees, auxiliary values use V, and frequency uses Hz.
                """
                if parameter <= MeasurementParameter.R:
                    return self._offset_value(parameter, value)
                if parameter == MeasurementParameter.PHASE:
                    return math.degrees(cmath.phase(value))
                if parameter <= MeasurementParameter.AUX_IN_4:
                    return self._aux_inputs[parameter - 5]
                if parameter == MeasurementParameter.REFERENCE_FREQUENCY:
                    return self._reference_frequency()
                return self._display_value(parameter - 9, value)

            if key == "OUTR":
                return self._format_values(self._display_value(int(args[0]), value))
            return self._format_values(*(measurement(int(arg)) for arg in args))
        if key == "FREQ":
            return self._format_values(self._reference_frequency())
        if key in self._settings:
            return self._format_values(self._settings[key])
        self._registers["standard_event"] |= int(StandardEventFlag.COMMAND_ERROR)
        raise pyvisa.errors.VisaIOError(StatusCode.error_timeout)

    def _raw_query_ascii_values(self, command: str) -> list[str]:
        """Split a raw text response, preserving empty trailing trace fields."""
        return self._raw_query(command).split(",")

    def _raw_read_buffer_bytes(self, command: str, size: int) -> bytes:
        """Return exactly size headerless bytes for a binary trace query.

        The public buffer reader has validated its range and acquisition state.
        Encode TRCB? values as little-endian IEEE floats, or TRCL? values as
        signed mantissa/exponent pairs (value = mantissa * 2**(exponent - 124)).
        No transport framing changes are needed. Raise OSError for a short
        response; the inherited wrapper performs post-transfer fault checks.
        """
        self._check_connected()
        self._check_synchronized()
        values = [
            float(field) for field in self._raw_query(command).split(",") if field
        ]
        if command.startswith("TRCB"):
            data = struct.pack(f"<{len(values)}f", *values)
        else:
            words: list[int] = []
            for value in values:
                if value == 0:
                    words.extend((0, 124))
                else:
                    mantissa, exponent = math.frexp(value)
                    word = round(mantissa * 32768)
                    if word > 32767:
                        word //= 2
                        exponent += 1
                    words.extend((word, exponent + 109))
            data = struct.pack(f"<{len(words)}h", *words)
        if len(data) != size:
            raise OSError("Incomplete virtual binary response.")
        return data

    def _recover_after_timeout(self) -> bool:
        """Confirm recovery is safe because the model has no delayed output.

        Text responses are synchronous. A timed-out unsupported query cannot
        leave a stale response that could be mistaken for an error register.
        """
        self._check_connected()
        return True

    @contextmanager
    def _io_timeout(self, seconds: float) -> Generator[None, None, None]:
        """Temporarily set the internal I/O budget in seconds.

        Restore the previous budget on success or failure. The inherited wait,
        FAST-read, and timeout-recovery methods use this context manager.
        """
        self._check_connected()
        previous = self._virtual_timeout
        self._virtual_timeout = seconds
        try:
            yield
        finally:
            self._virtual_timeout = previous

    def _discard_fast_data(self) -> None:
        """Discard queued FAST pairs after the caller has stopped streaming."""
        self._check_connected()
        self._fast_queue.clear()

    def _read_fast_bytes(self, size: int) -> bytes:
        """Wait for size FAST bytes, packed as little-endian signed X/Y pairs.

        Catch up acquisition, consume queued pairs, and sleep until the next
        scheduled sample or timeout. Triggered/paused scans are polled for new
        data. Raise a VISA timeout when the temporary I/O budget expires; the
        inherited read_fast_data method handles stream cleanup and translation.
        """
        self._check_connected()
        deadline = time.monotonic() + self._virtual_timeout
        result = bytearray()
        while len(result) < size:
            self._update_state()
            if self._fast_queue:
                result.extend(struct.pack("<hh", *self._fast_queue.popleft()))
                continue
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                raise pyvisa.errors.VisaIOError(StatusCode.error_timeout)
            if not self._running or self._settings["SRAT"] == SampleRate.TRIGGER:
                delay = 0.01
            else:
                rate = 0.0625 * 2 ** int(self._settings["SRAT"])
                delay = max(1e-9, self._last_sample + 1 / rate - now)
            time.sleep(min(delay, remaining))
        return bytes(result)

    @staticmethod
    def _format_values(*values: float | int) -> str:
        """Serialize numeric response fields, using integer codes for enums.

        IntEnum string formatting differs across supported Python versions.
        Normalize integral fields here while preserving floating-point values;
        the model can retain enum members internally without leaking names.
        """
        return ",".join(
            str(int(value)) if isinstance(value, int) else str(value)
            for value in values
        )

    # --- Instrument state, filtering, and acquisition ---

    def _reset_state(self) -> None:
        """Restore instrument defaults and clear acquisition/filter state.

        Preserve input amplitude/phase, external conditions, saved setups, status
        registers, OUTX, and *PSC. An empty initial settings dictionary uses GPIB
        and disabled power-on clearing as fallbacks. Reinitialize all four filter
        stages at the current input so reset starts at steady state. Normal reads
        and writes subsequently evolve that state with elapsed time.
        """
        output = self._settings.get("OUTX", OutputInterface.GPIB)
        power_on_clear = self._settings.get("*PSC", SwitchState.OFF)
        self._settings = {
            "PHAS": 0.0,
            "FMOD": ReferenceSource.INTERNAL,
            "FREQ": 1000.0,
            "HARM": 1,
            "RSLP": ReferenceTrigger.ZERO_CROSSING,
            "SLVL": 1.0,
            "ISRC": InputConfiguration.A,
            "IGND": InputShieldGrounding.FLOAT,
            "ICPL": InputCoupling.AC,
            "ILIN": LineNotchFilter.OFF,
            "SENS": Sensitivity.x1,
            "RMOD": ReserveMode.LOW_NOISE,
            "OFLT": TimeConstant.ms_100,
            "OFSL": LowPassFilterSlope.dB_12,
            "SYNC": SynchronousFilter.OFF,
            "OUTX": output,
            "KCLK": SwitchState.ON,
            "ALRM": SwitchState.ON,
            "SRAT": SampleRate.Hz_1,
            "SEND": EndOfBufferMode.LOOP,
            "TSTR": TriggerStartMode.OFF,
            "FAST": DataTransferMode.OFF,
            "LOCL": LocalMode.LOCAL,
            "OVRM": GpibOverrideRemote.ENABLED,
            "*PSC": power_on_clear,
        }
        self._aux_outputs = [0.0] * 4
        self._displays: list[tuple[int, int]] = [
            (Channel1Display.X, Channel1Ratio.NONE),
            (Channel2Display.Y, Channel2Ratio.NONE),
        ]
        self._front_outputs: list[int] = [FrontPanelOutputSource.COMPONENT] * 2
        self._offsets: list[tuple[float, int]] = [(0.0, OutputExpansion.x1)] * 3
        self._buffers: list[deque[float]] = [deque(maxlen=16383), deque(maxlen=16383)]
        self._fast_queue: deque[tuple[int, int]] = deque()
        self._running = False
        self._scan_started = False
        self._last_sample = time.monotonic()
        self._filter_time = time.monotonic()
        self._filters = [self._input_target()] * 4

    def _input_target(self) -> complex:
        """Return the unfiltered complex RMS input, before reference rotation.

        The real/imaginary components are amplitude*cos(phase) and
        amplitude*sin(phase), with phase converted from degrees to radians.
        An unlocked external reference produces zero demodulated input.
        """
        if (
            self._settings["FMOD"] == ReferenceSource.EXTERNAL
            and not self._external_locked
        ):
            return 0j
        return self._amplitude * cmath.exp(1j * math.radians(self._phase))

    def _filter_at(self, when: float) -> complex:
        """Evolve the cascaded low-pass filter to an absolute monotonic time.

        Parameters
        ----------
        when : float
            Monotonic timestamp in seconds; internal callers process sample
            timestamps in order before updating to the present time.

        Returns
        -------
        complex
            RMS X/Y in V or A after the selected number of filter stages and
            rotation by the negative instrument reference phase.

        Notes
        -----
        Update all four stages analytically for a constant source between state
        changes. The slope selects one to four stages, each with the chosen time
        constant. Treat more than 100 time constants as fully settled. Calls
        mutate the filter history; elapsed time is never negative.
        """
        dt = max(0.0, when - self._filter_time)
        tau = _time_constant_seconds(int(self._settings["OFLT"]))
        ratio = dt / tau
        target = self._input_target()
        if ratio > 100:
            self._filters = [target] * 4
        elif dt:
            previous = self._filters[:]
            for stage in range(4):
                self._filters[stage] = target + math.exp(-ratio) * sum(
                    (previous[stage - k] - target) * ratio**k / math.factorial(k)
                    for k in range(stage + 1)
                )
        self._filter_time = max(self._filter_time, when)
        return self._filters[int(self._settings["OFSL"])] * cmath.exp(
            -1j * math.radians(self._settings["PHAS"])
        )

    def _update_state(self) -> None:
        """Catch up acquisition and filter state to the current time.

        Generate periodic samples at their scheduled timestamps, then evolve the
        filter to now. Triggered acquisition records points only through TRIG.
        Limit catch-up work to buffer capacity after long idle periods and latch
        output overload when the filtered magnitude exceeds full scale.
        """
        now = time.monotonic()
        if self._running and self._settings["SRAT"] != SampleRate.TRIGGER:
            rate = 0.0625 * 2 ** int(self._settings["SRAT"])
            count = max(0, int((now - self._last_sample) * rate + 1e-9))
            # Avoid unbounded work after a long real-world idle period. Retain the
            # same latest samples that fit in the physical instrument's buffer.
            if self._settings["SEND"] == EndOfBufferMode.ONE_SHOT:
                count = min(count, 16383 - len(self._buffers[0]))
            elif count > 16383:
                self._last_sample += (count - 16383) / rate
                count = 16383
            for _ in range(count):
                self._last_sample += 1 / rate
                self._store_sample(self._last_sample)
        value = self._filter_at(now)
        if abs(value) > self._full_scale():
            self._registers["lia_status"] |= int(LiaStatusFlag.OUTPUT_OVERLOAD)

    def _store_sample(self, when: float) -> None:
        """Store a sample at an absolute monotonic timestamp in seconds.

        Record both channel displays, including their offsets and ratios. If FAST
        is enabled, enqueue signed X/Y counts including expansion; +/-30000
        represents full scale before expansion. FAST2 queue overflow latches a
        GPIB error and disables transfer. Reaching one-shot capacity ends the scan.
        """
        value = self._filter_at(when)
        self._buffers[0].append(self._display_value(1, value))
        self._buffers[1].append(self._display_value(2, value))
        if self._settings["FAST"] != DataTransferMode.OFF:
            full_scale = self._full_scale()
            counts = []
            for raw, (offset, expand) in zip(
                (value.real, value.imag), self._offsets[:2]
            ):
                count = round(
                    (raw / full_scale - offset / 100) * (1, 10, 100)[expand] * 30000
                )
                counts.append(max(-32768, min(32767, count)))
            # FAST2 has a 63-pair output queue. Model an aborted transfer rather
            # than allowing virtual applications to ignore the real constraint.
            if (
                self._settings["FAST"] == DataTransferMode.WINDOWS
                and len(self._fast_queue) >= 63
            ):
                self._settings["FAST"] = DataTransferMode.OFF
                self._registers["error"] |= int(ErrorFlag.GPIB_ERROR)
            else:
                self._fast_queue.append((counts[0], counts[1]))
        if abs(value) > self._full_scale():
            self._registers["lia_status"] |= int(LiaStatusFlag.OUTPUT_OVERLOAD)
        if (
            self._settings["SEND"] == EndOfBufferMode.ONE_SHOT
            and len(self._buffers[0]) == 16383
        ):
            self._running = False
            self._scan_started = False

    def _full_scale(self) -> float:
        """Return the selected RMS full-scale amplitude in V or A.

        Convert the sensitivity command code using the active voltage/current
        input configuration. The result uses the same units as source amplitude.
        """
        return _full_scale(int(self._settings["SENS"]), int(self._settings["ISRC"]))

    def _offset_value(self, parameter: int, value: complex) -> float:
        """Apply the configured percentage offset to X, Y, or R.

        Parameters
        ----------
        parameter : int
            OutputParameter command code for X, Y, or R (1 through 3).
        value : complex
            Filtered, reference-rotated RMS input in V or A.

        Returns
        -------
        float
            Offset-adjusted component in V or A. Expansion changes resolution and
            FAST counts, rather than scaling ordinary measurement amplitudes.
        """
        raw = (value.real, value.imag, abs(value))[parameter - 1]
        offset, _ = self._offsets[parameter - 1]
        return raw - offset / 100 * self._full_scale()

    def _display_value(self, channel: int, value: complex) -> float:
        """Calculate a channel display from the filtered complex RMS input.

        Parameters
        ----------
        channel : int
            Display channel 1 or 2.
        value : complex
            Filtered, reference-rotated RMS X/Y components.

        Returns
        -------
        float
            Selected component/magnitude in V or A, phase in degrees, auxiliary
            voltage, ideal noise density (zero), or clipped ratio percentage.

        Notes
        -----
        Apply channel-specific display and auxiliary denominator selections.
        A zero ratio denominator returns zero and latches output overload.
        """
        display, ratio = self._displays[channel - 1]
        if display in (Channel1Display.X, Channel2Display.Y):
            result = self._offset_value(channel, value)
        elif display in (Channel1Display.R, Channel2Display.PHASE):
            result = (
                self._offset_value(3, value)
                if channel == Channel.CH1
                else math.degrees(cmath.phase(value))
            )
        elif display in (Channel1Display.X_NOISE, Channel2Display.Y_NOISE):
            result = 0.0  # Ideal input: no injected noise density.
        else:
            result = self._aux_inputs[
                display - 3 + (0 if channel == Channel.CH1 else 2)
            ]
        if ratio:
            denominator = self._aux_inputs[
                ratio - 1 + (0 if channel == Channel.CH1 else 2)
            ]
            if denominator == 0:
                self._registers["lia_status"] |= int(LiaStatusFlag.OUTPUT_OVERLOAD)
                return 0.0
            # Ratio displays are percentages of full scale per volt of aux input.
            scale = self._full_scale()
            expand = 1
            if display in (Channel1Display.X, Channel2Display.Y):
                expand = (1, 10, 100)[self._offsets[channel - 1][1]]
            elif display in (Channel1Display.R, Channel2Display.PHASE):
                if channel == Channel.CH1:
                    expand = (1, 10, 100)[self._offsets[2][1]]
                else:
                    scale = 180.0
            elif display >= Channel1Display.AUX_IN_1:
                scale = 10.0
            result = max(
                -100.0, min(100.0, result / scale * expand * 100 / denominator)
            )
        return result

    def _status_byte(self, acknowledge: bool = False) -> int:
        """Compute the serial-poll byte, optionally acknowledging an SRQ.

        First catch up the model. Summarize event registers through their enable
        masks, report pending FAST output, and mark commands ready because command
        execution is instantaneous. A paused scan still counts as started until
        reset or one-shot completion; this byte does not distinguish pause.

        Parameters
        ----------
        acknowledge : bool, optional
            Acknowledge an asserted service request, as a native serial poll does.
            Reading status leaves event registers latched.
        """
        self._update_state()
        result = 0
        if not self._scan_started:
            result |= int(SerialPollFlag.NO_SCAN_IN_PROGRESS)
        result |= int(SerialPollFlag.NO_COMMAND_IN_PROGRESS)
        for register, flag in [
            ("error", SerialPollFlag.ERROR),
            ("lia_status", SerialPollFlag.LIA_STATUS),
            ("standard_event", SerialPollFlag.STANDARD_EVENT),
        ]:
            if self._registers[register] & self._enables[register]:
                result |= int(flag)
        if self._fast_queue:
            result |= int(SerialPollFlag.MESSAGE_AVAILABLE)
        requesting = bool(result & self._enables["serial_poll"])
        if requesting and (not acknowledge or not self._srq_acknowledged):
            result |= int(SerialPollFlag.SERVICE_REQUEST)
        if acknowledge and requesting:
            self._srq_acknowledged = True
        if not requesting:
            self._srq_acknowledged = False
        return result

    def _reference_frequency(self) -> float:
        """Return the reference frequency in Hz.

        Use the internal oscillator setting or the supplied external frequency.
        An unlocked external reference reads zero.
        """
        return (
            float(self._settings["FREQ"])
            if self._settings["FMOD"] == ReferenceSource.INTERNAL
            else (self._external_frequency if self._external_locked else 0.0)
        )
