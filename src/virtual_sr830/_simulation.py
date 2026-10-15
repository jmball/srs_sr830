"""In-memory SR830 protocol/state model used by VirtualSR830.

This is a deterministic demodulated-signal model, not an electrical SPICE model.
It models filter settling, phase, displays, registers, and acquisition together.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import cmath
import copy
import math
import struct

from sr830.settings import (
    EndOfBufferMode,
    ErrorFlag,
    LiaStatusFlag,
    SerialPollFlag,
    StandardEventFlag,
    _ENABLE_REGISTER_COMMANDS,
    _STATUS_REGISTER_COMMANDS,
    _full_scale,
    _time_constant_seconds,
)


class Simulation:
    def __init__(
        self, clock: Callable[[], float], signal: Callable[[float], complex] | None
    ) -> None:
        self.clock = clock
        self.signal = signal
        self.input = complex(0.001, 0)
        self.external_frequency = 1000.0
        self.external_locked = True
        self.aux_inputs = [0.0] * 4
        self.setups: dict[
            int,
            tuple[
                dict[str, float | int],
                list[float],
                list[tuple[int, int]],
                list[tuple[float, int]],
                list[int],
            ],
        ] = {}
        self.offset_time = 0.0
        self.registers = {
            name: 0 for name in ("standard_event", "serial_poll", "error", "lia_status")
        }
        self.enables = self.registers.copy()
        self.srq_acknowledged = False
        self.settings: dict[str, float | int] = {}
        self.reset()

    def now(self) -> float:
        return self.clock() + self.offset_time

    def reset(self) -> None:
        # *RST preserves communications and status registers (manual, 4-4/5-19).
        output = self.settings.get("OUTX", 1)
        self.settings = dict(
            PHAS=0.0,
            FMOD=1,
            FREQ=1000.0,
            HARM=1,
            RSLP=0,
            SLVL=1.0,
            ISRC=0,
            IGND=0,
            ICPL=0,
            ILIN=0,
            SENS=26,
            RMOD=2,
            OFLT=8,
            OFSL=1,
            SYNC=0,
            OUTX=output,
            KCLK=1,
            ALRM=1,
            SRAT=4,
            SEND=1,
            TSTR=0,
            FAST=0,
            LOCL=0,
            OVRM=1,
            **{"*PSC": self.settings.get("*PSC", 0)},
        )
        self.aux_outputs = [0.0] * 4
        self.displays = [(0, 0), (0, 0)]
        self.front_outputs = [1, 1]
        self.offsets = [(0.0, 0)] * 3
        self.buffers: list[deque[float]] = [deque(maxlen=16383), deque(maxlen=16383)]
        self.fast: deque[tuple[int, int]] = deque()
        self.running = False
        self.scan_started = False
        self.last_sample = self.now()
        self.filter_time = self.now()
        self.filters = [self.target(self.now())] * 4
        self.busy_until = self.now()

    def target(self, when: float) -> complex:
        if self.settings.get("FMOD", 1) == 0 and not self.external_locked:
            return 0j
        value = complex(self.signal(when)) if self.signal is not None else self.input
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError("The signal callback must return finite components.")
        return value

    def filter_at(self, when: float) -> complex:
        dt = max(0.0, when - self.filter_time)
        tau = _time_constant_seconds(int(self.settings["OFLT"]))
        ratio = dt / tau
        target = self.target(when)
        if ratio > 100:
            self.filters = [target] * 4
        elif dt:
            previous = self.filters[:]
            for stage in range(4):
                self.filters[stage] = target + math.exp(-ratio) * sum(
                    (previous[stage - k] - target) * ratio**k / math.factorial(k)
                    for k in range(stage + 1)
                )
        self.filter_time = max(self.filter_time, when)
        return self.filters[int(self.settings["OFSL"])] * cmath.exp(
            -1j * math.radians(self.settings["PHAS"])
        )

    def update(self) -> None:
        now = self.now()
        if self.running and self.settings["SRAT"] != 14:
            rate = 0.0625 * 2 ** int(self.settings["SRAT"])
            count = max(0, int((now - self.last_sample) * rate + 1e-9))
            # Avoid unbounded work after a long real-world idle period. Retain the
            # same latest samples that fit in the physical instrument's buffer.
            if self.settings["SEND"] == EndOfBufferMode.ONE_SHOT:
                count = min(count, 16383 - len(self.buffers[0]))
            elif count > 16383:
                self.last_sample += (count - 16383) / rate
                count = 16383
            for _ in range(count):
                self.last_sample += 1 / rate
                self.sample(self.last_sample)
        value = self.filter_at(now)
        if abs(value) > self.full_scale():
            self.registers["lia_status"] |= int(LiaStatusFlag.OUTPUT_OVERLOAD)

    def sample(self, when: float) -> None:
        value = self.filter_at(when)
        self.buffers[0].append(self.display(1, value))
        self.buffers[1].append(self.display(2, value))
        if self.settings["FAST"]:
            full_scale = self.full_scale()
            counts = []
            for raw, (offset, expand) in zip(
                (value.real, value.imag), self.offsets[:2]
            ):
                count = round(
                    (raw / full_scale - offset / 100) * (1, 10, 100)[expand] * 30000
                )
                counts.append(max(-32768, min(32767, count)))
            # FAST2 has a 63-pair output queue. Model an aborted transfer rather
            # than allowing virtual applications to ignore the real constraint.
            if self.settings["FAST"] == 2 and len(self.fast) >= 63:
                self.settings["FAST"] = 0
                self.registers["error"] |= int(ErrorFlag.GPIB_ERROR)
            else:
                self.fast.append((counts[0], counts[1]))
        if abs(value) > self.full_scale():
            self.registers["lia_status"] |= int(LiaStatusFlag.OUTPUT_OVERLOAD)
        if (
            self.settings["SEND"] == EndOfBufferMode.ONE_SHOT
            and len(self.buffers[0]) == 16383
        ):
            self.running = False
            self.scan_started = False

    def full_scale(self) -> float:
        return _full_scale(int(self.settings["SENS"]), int(self.settings["ISRC"]))

    def adjusted(self, parameter: int, value: complex) -> float:
        raw = (value.real, value.imag, abs(value))[parameter - 1]
        offset, _ = self.offsets[parameter - 1]
        return raw - offset / 100 * self.full_scale()

    def display(self, channel: int, value: complex) -> float:
        display, ratio = self.displays[channel - 1]
        if display == 0:
            result = self.adjusted(channel, value)
        elif display == 1:
            result = (
                self.adjusted(3, value)
                if channel == 1
                else math.degrees(cmath.phase(value))
            )
        elif display == 2:
            result = 0.0  # Ideal input: no injected noise density.
        else:
            result = self.aux_inputs[display - 3 + (0 if channel == 1 else 2)]
        if ratio:
            denominator = self.aux_inputs[ratio - 1 + (0 if channel == 1 else 2)]
            if denominator == 0:
                self.registers["lia_status"] |= int(LiaStatusFlag.OUTPUT_OVERLOAD)
                return 0.0
            # Ratio displays are percentages of full scale per volt of aux input.
            scale = self.full_scale()
            expand = 1
            if display == 0:
                expand = (1, 10, 100)[self.offsets[channel - 1][1]]
            elif display == 1:
                if channel == 1:
                    expand = (1, 10, 100)[self.offsets[2][1]]
                else:
                    scale = 180.0
            elif display >= 3:
                scale = 10.0
            result = max(
                -100.0, min(100.0, result / scale * expand * 100 / denominator)
            )
        return result

    def status(self, acknowledge: bool = False) -> int:
        self.update()
        result = 0
        if not self.scan_started:
            result |= int(SerialPollFlag.NO_SCAN_IN_PROGRESS)
        if self.now() >= self.busy_until:
            result |= int(SerialPollFlag.NO_COMMAND_IN_PROGRESS)
        for register, flag in [
            ("error", SerialPollFlag.ERROR),
            ("lia_status", SerialPollFlag.LIA_STATUS),
            ("standard_event", SerialPollFlag.STANDARD_EVENT),
        ]:
            if self.registers[register] & self.enables[register]:
                result |= int(flag)
        if self.fast:
            result |= int(SerialPollFlag.MESSAGE_AVAILABLE)
        requesting = bool(result & self.enables["serial_poll"])
        if requesting and (not acknowledge or not self.srq_acknowledged):
            result |= int(SerialPollFlag.SERVICE_REQUEST)
        if acknowledge and requesting:
            self.srq_acknowledged = True
        if not requesting:
            self.srq_acknowledged = False
        return result

    def write(self, command: str) -> None:
        self.update()
        key, _, arguments = command.strip().partition(" ")
        args = [part.strip() for part in arguments.split(",")] if arguments else []
        if key == "*RST":
            self.reset()
        elif key == "*CLS":
            for register in self.registers:
                self.registers[register] = 0
            self.srq_acknowledged = False
        elif key in ("*ESE", "*SRE", "ERRE", "LIAE"):
            register = next(
                name
                for name, mnemonic in _ENABLE_REGISTER_COMMANDS.items()
                if mnemonic == key
            )
            if len(args) == 2:
                bit, state = map(int, args)
                self.enables[register] = (self.enables[register] & ~(1 << bit)) | (
                    state << bit
                )
            else:
                self.enables[register] = int(args[0])
            self.srq_acknowledged = False
        elif key == "DDEF":
            channel, display, ratio = map(int, args)
            self.displays[channel - 1] = (display, ratio)
        elif key == "FPOP":
            self.front_outputs[int(args[0]) - 1] = int(args[1])
        elif key == "OEXP":
            self.offsets[int(args[0]) - 1] = (float(args[1]), int(args[2]))
        elif key == "AUXV":
            self.aux_outputs[int(args[0]) - 1] = float(args[1])
        elif key in ("SSET", "RSET"):
            number = int(args[0])
            if key == "SSET":
                self.setups[number] = copy.deepcopy(
                    (
                        self.settings,
                        self.aux_outputs,
                        self.displays,
                        self.offsets,
                        self.front_outputs,
                    )
                )
            elif number not in self.setups:
                self.registers["standard_event"] |= int(
                    StandardEventFlag.EXECUTION_ERROR
                )
                raise ValueError(f"No setup saved in slot {number}.")
            else:
                preserved = {
                    key: self.settings[key] for key in ("OUTX", "LOCL", "OVRM", "*PSC")
                }
                (
                    self.settings,
                    self.aux_outputs,
                    self.displays,
                    self.offsets,
                    self.front_outputs,
                ) = copy.deepcopy(self.setups[number])
                self.settings.update(preserved)
        elif key in ("STRT", "STRD"):
            if not self.running:
                self.running = self.scan_started = True
                self.last_sample = self.now() + (0.5 if key == "STRD" else 0.0)
        elif key == "PAUS":
            self.running = False
        elif key == "REST":
            self.running = self.scan_started = False
            for buffer in self.buffers:
                buffer.clear()
            self.fast.clear()
        elif key == "TRIG":
            self.registers["lia_status"] |= int(LiaStatusFlag.TRIGGER)
            if self.settings["TSTR"] and not self.running:
                self.running = self.scan_started = True
                self.last_sample = self.now()
                return
            if self.running and self.settings["SRAT"] == 14:
                self.sample(self.now())
        elif key in ("AGAN", "ARSV", "APHS", "AOFF"):
            value = self.filter_at(self.now())
            if key == "APHS":
                self.settings["PHAS"] = float(self.settings["PHAS"]) + math.degrees(
                    cmath.phase(value)
                )
            elif (
                key == "AGAN"
                and _time_constant_seconds(int(self.settings["OFLT"])) <= 1
            ):
                amplitude = abs(value)
                code = next(
                    (
                        i
                        for i in range(27)
                        if _full_scale(i, int(self.settings["ISRC"])) >= amplitude
                    ),
                    26,
                )
                self.settings["SENS"] = code
            elif key == "ARSV":
                self.settings["RMOD"] = 2
            elif key == "AOFF":
                parameter = int(args[0])
                raw = (value.real, value.imag, abs(value))[parameter - 1]
                _, expand = self.offsets[parameter - 1]
                self.offsets[parameter - 1] = (
                    max(-105.0, min(105.0, raw / self.full_scale() * 100)),
                    expand,
                )
            self.busy_until = self.now() + 0.05
        elif key in self.settings:
            if key == "FREQ" and not self.settings["FMOD"]:
                raise ValueError(
                    "Internal frequency is writable only in internal reference mode."
                )
            value_number = (
                float(args[0]) if key in ("PHAS", "FREQ", "SLVL") else int(args[0])
            )
            self.settings[key] = value_number
            if key in ("OFLT", "ISRC", "SENS"):
                if key == "OFLT" and value_number != 0:
                    self.registers["lia_status"] |= int(
                        LiaStatusFlag.TIME_CONSTANT_CHANGED
                    )
            if key == "HARM":
                frequency = self.frequency()
                if frequency > 0:
                    self.settings["HARM"] = min(
                        int(value_number), max(1, int(102000 / frequency))
                    )
            if key == "SENS" and value_number >= 21 and self.settings["ISRC"] == 3:
                self.settings["ISRC"] = 2
            if key == "FAST" and not value_number:
                self.fast.clear()
        else:
            self.registers["standard_event"] |= int(StandardEventFlag.COMMAND_ERROR)
            raise ValueError(f"Unsupported virtual command: {command}.")

    def frequency(self) -> float:
        return (
            float(self.settings["FREQ"])
            if self.settings["FMOD"]
            else (self.external_frequency if self.external_locked else 0.0)
        )

    def query(self, command: str) -> str:
        self.update()
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
                self.enables[register]
                if is_enable
                else (self.status() if key == "*STB" else self.registers[register])
            )
            result = ((byte >> int(args[0])) & 1) if args else byte
            if not is_enable and key != "*STB":
                self.registers[register] &= ~(1 << int(args[0])) if args else 0
            return str(result)
        if key in ("DDEF", "FPOP", "OEXP", "OAUX", "AUXV"):
            index = int(args[0]) - 1
            if key == "DDEF":
                return ",".join(map(str, self.displays[index]))
            if key == "FPOP":
                return str(self.front_outputs[index])
            if key == "OEXP":
                return ",".join(map(str, self.offsets[index]))
            return str((self.aux_inputs if key == "OAUX" else self.aux_outputs)[index])
        if key == "SPTS":
            return str(len(self.buffers[0]))
        if key in ("TRCA", "TRCB", "TRCL"):
            channel, start, bins = map(int, args)
            return (
                ",".join(
                    map(str, list(self.buffers[channel - 1])[start : start + bins])
                )
                + ","
            )
        if key in ("OUTP", "OUTR", "SNAP"):
            value = self.filter_at(self.now())

            def measurement(parameter: int) -> float:
                if parameter <= 3:
                    return self.adjusted(parameter, value)
                if parameter == 4:
                    return math.degrees(cmath.phase(value))
                if parameter <= 8:
                    return self.aux_inputs[parameter - 5]
                if parameter == 9:
                    return self.frequency()
                return self.display(parameter - 9, value)

            if key == "OUTR":
                return str(self.display(int(args[0]), value))
            return ",".join(str(measurement(int(arg))) for arg in args)
        if key == "FREQ":
            return str(self.frequency())
        if key in self.settings:
            return str(self.settings[key])
        raise ValueError(f"Unsupported virtual query: {command}.")

    def buffer_bytes(self, command: str) -> bytes:
        values = [float(field) for field in self.query(command).split(",") if field]
        if command.startswith("TRCB"):
            return struct.pack(f"<{len(values)}f", *values)
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
        return struct.pack(f"<{len(words)}h", *words)
