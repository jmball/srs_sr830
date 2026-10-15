"""SR830 setting enums and internal protocol helpers.

Integer enum values are instrument command codes, not physical values.
Unit-valued settings use <unit>_<value>; multiplier settings use x<value>.
SI prefixes in numbers use n (nano), u (micro), and m (milli).
"""

from collections.abc import Mapping
from enum import Enum, IntEnum, IntFlag
from numbers import Integral
from types import MappingProxyType


class ReferenceSource(IntEnum):
    """Reference oscillator source (FMOD)."""

    EXTERNAL = 0
    INTERNAL = 1


class ReferenceTrigger(IntEnum):
    """External reference trigger edge (RSLP)."""

    ZERO_CROSSING = 0
    TTL_RISING_EDGE = 1
    TTL_FALLING_EDGE = 2


class InputConfiguration(IntEnum):
    """Input configuration (ISRC).

    A selects voltage input A; A_MINUS_B selects differential voltage input.
    CURRENT_1_MOHM and CURRENT_100_MOHM select current input with 1 or
    100 megohm transimpedance gain respectively.
    """

    A = 0
    A_MINUS_B = 1
    CURRENT_1_MOHM = 2
    CURRENT_100_MOHM = 3


class InputShieldGrounding(IntEnum):
    """Input shield grounding (IGND)."""

    FLOAT = 0
    GROUND = 1


class InputCoupling(IntEnum):
    """Input coupling (ICPL)."""

    AC = 0
    DC = 1


class LineNotchFilter(IntEnum):
    """Line-frequency notch filters (ILIN)."""

    OFF = 0
    LINE = 1
    SECOND_HARMONIC = 2
    BOTH = 3


class ReserveMode(IntEnum):
    """Dynamic reserve mode (RMOD): high reserve, normal, or low noise."""

    HIGH_RESERVE = 0
    NORMAL = 1
    LOW_NOISE = 2


class SynchronousFilter(IntEnum):
    """Synchronous filter state (SYNC).

    OFF disables the filter. BELOW_200_HZ enables it when the detection
    frequency (reference frequency times harmonic) is below 200 Hz.
    """

    OFF = 0
    BELOW_200_HZ = 1


class Channel1Display(IntEnum):
    """Channel 1 display quantity (DDEF)."""

    X = 0
    R = 1
    X_NOISE = 2
    AUX_IN_1 = 3
    AUX_IN_2 = 4


class Channel2Display(IntEnum):
    """Channel 2 display quantity (DDEF)."""

    Y = 0
    PHASE = 1
    Y_NOISE = 2
    AUX_IN_3 = 3
    AUX_IN_4 = 4


class Channel1Ratio(IntEnum):
    """Channel 1 display ratio denominator (DDEF)."""

    NONE = 0
    AUX_IN_1 = 1
    AUX_IN_2 = 2


class Channel2Ratio(IntEnum):
    """Channel 2 display ratio denominator (DDEF)."""

    NONE = 0
    AUX_IN_3 = 1
    AUX_IN_4 = 2


class FrontPanelOutputSource(IntEnum):
    """Front-panel output source (FPOP).

    DISPLAY selects the channel's displayed quantity. COMPONENT selects X
    for channel 1 and Y for channel 2.
    """

    DISPLAY = 0
    COMPONENT = 1


class OutputInterface(IntEnum):
    """Instrument-side response interface (OUTX)."""

    RS232 = 0
    GPIB = 1


class SwitchState(IntEnum):
    """Off/on codes for key clicks, alarm, and power-on status clearing."""

    OFF = 0
    ON = 1


class EndOfBufferMode(IntEnum):
    """Data buffer storage mode (SEND)."""

    ONE_SHOT = 0
    LOOP = 1


class TriggerStartMode(IntEnum):
    """Trigger-start behavior (TSTR)."""

    OFF = 0
    START_SCAN = 1


class DataTransferMode(IntEnum):
    """GPIB fast transfer mode (FAST).

    OFF disables transfer. DOS selects dedicated collection; WINDOWS selects
    buffered transfer for hosts that may be interrupted. These are instrument
    mode names and do not restrict the operating system running the driver.
    """

    OFF = 0
    DOS = 1
    WINDOWS = 2


class LocalMode(IntEnum):
    """Local, remote, or front-panel lockout mode (LOCL).

    LOCAL enables front-panel control, REMOTE permits return via the Local
    key, and LOCAL_LOCKOUT disables that key. The caller selects this mode.
    """

    LOCAL = 0
    REMOTE = 1
    LOCAL_LOCKOUT = 2


class GpibOverrideRemote(IntEnum):
    """GPIB remote override state (OVRM).

    ENABLED keeps the front panel usable despite GPIB remote control;
    DISABLED restores normal GPIB remote behavior.
    """

    DISABLED = 0
    ENABLED = 1


class Sensitivity(IntEnum):
    """SENS codes for RMS full-scale amplitudes, not gains.

    Names use ``x<number><SI prefix>`` (``u`` means micro); ``x1`` is unity.
    The full-scale multiplier applies to V for voltage inputs or microamps
    for current inputs: ``x1u`` selects 1 microvolt or 1 picoamp. It does not
    represent amplifier gain. Enum values are instrument command codes.
    """

    x2n = 0
    x5n = 1
    x10n = 2
    x20n = 3
    x50n = 4
    x100n = 5
    x200n = 6
    x500n = 7
    x1u = 8
    x2u = 9
    x5u = 10
    x10u = 11
    x20u = 12
    x50u = 13
    x100u = 14
    x200u = 15
    x500u = 16
    x1m = 17
    x2m = 18
    x5m = 19
    x10m = 20
    x20m = 21
    x50m = 22
    x100m = 23
    x200m = 24
    x500m = 25
    x1 = 26


class TimeConstant(IntEnum):
    """Time-constant codes (OFLT), named <unit>_<value>.

    Units are us (microseconds), ms (milliseconds), s (seconds), and ks
    (kiloseconds). For example, ms_100 means 100 ms; its command code is 8.
    The instrument may restrict the selected time constant based on detection
    frequency, filter slope, and dynamic reserve.
    """

    us_10 = 0
    us_30 = 1
    us_100 = 2
    us_300 = 3
    ms_1 = 4
    ms_3 = 5
    ms_10 = 6
    ms_30 = 7
    ms_100 = 8
    ms_300 = 9
    s_1 = 10
    s_3 = 11
    s_10 = 12
    s_30 = 13
    s_100 = 14
    s_300 = 15
    ks_1 = 16
    ks_3 = 17
    ks_10 = 18
    ks_30 = 19


class LowPassFilterSlope(IntEnum):
    """Filter-slope codes (OFSL), named dB_<value>.

    dB_6, dB_12, dB_18, and dB_24 select slopes of 6, 12, 18, and 24
    decibels per octave respectively. Their command codes are 0 through 3.
    """

    dB_6 = 0
    dB_12 = 1
    dB_18 = 2
    dB_24 = 3


class OutputExpansion(IntEnum):
    """Output-expansion codes (OEXP), named x<value>.

    x1, x10, and x100 select expansion factors of 1, 10, and 100.
    Code 0 means no expansion (unity gain); it does not mean zero gain.
    """

    x1 = 0
    x10 = 1
    x100 = 2


class SampleRate(IntEnum):
    """Sample-rate codes (SRAT), named <unit>_<value>.

    Hz means hertz and mHz means millihertz. An underscore replaces the
    decimal point in mHz_62_5 (62.5 mHz). TRIGGER selects sampling on each
    trigger rather than a periodic rate. Values are command codes 0 to 14.
    """

    mHz_62_5 = 0
    mHz_125 = 1
    mHz_250 = 2
    mHz_500 = 3
    Hz_1 = 4
    Hz_2 = 5
    Hz_4 = 6
    Hz_8 = 7
    Hz_16 = 8
    Hz_32 = 9
    Hz_64 = 10
    Hz_128 = 11
    Hz_256 = 12
    Hz_512 = 13
    TRIGGER = 14


class Channel(IntEnum):
    """Front-panel display, output, and buffer channel numbers."""

    CH1 = 1
    CH2 = 2


class AuxiliaryChannel(IntEnum):
    """Auxiliary input/output channel numbers."""

    AUX1 = 1
    AUX2 = 2
    AUX3 = 3
    AUX4 = 4


class OutputParameter(IntEnum):
    """Quantities supporting output offset and expansion (OEXP and AOFF)."""

    X = 1
    Y = 2
    R = 3


class MeasurementParameter(IntEnum):
    """SNAP selectors; OUTP (measure) accepts only X, Y, R, and PHASE."""

    X = 1
    Y = 2
    R = 3
    PHASE = 4
    AUX_IN_1 = 5
    AUX_IN_2 = 6
    AUX_IN_3 = 7
    AUX_IN_4 = 8
    REFERENCE_FREQUENCY = 9
    CH1_DISPLAY = 10
    CH2_DISPLAY = 11


class StatusRegister(str, Enum):
    """Register selectors; values retain the existing string names."""

    STANDARD_EVENT = "standard_event"
    SERIAL_POLL = "serial_poll"
    ERROR = "error"
    LIA_STATUS = "lia_status"


class StandardEventBit(IntEnum):
    """Standard-event register bit positions for the ``bit=`` argument.

    INPUT_QUEUE_OVERFLOW and OUTPUT_QUEUE_OVERFLOW report queue errors.
    EXECUTION_ERROR reports a command that cannot execute or an invalid
    parameter; COMMAND_ERROR reports an illegal command. USER_REQUEST
    reports a key/knob action and POWER_ON reports power-up. Bits 1 and 3
    are unused.
    """

    INPUT_QUEUE_OVERFLOW = 0
    OUTPUT_QUEUE_OVERFLOW = 2
    EXECUTION_ERROR = 4
    COMMAND_ERROR = 5
    USER_REQUEST = 6
    POWER_ON = 7


class StandardEventFlag(IntFlag):
    """StandardEvent register masks for whole-byte values; combine with ``|``.

    Member meanings are documented in StandardEventBit. Each mask is 1 shifted
    by the corresponding bit position; NONE means no bits are set.
    """

    NONE = 0
    INPUT_QUEUE_OVERFLOW = 1 << 0
    OUTPUT_QUEUE_OVERFLOW = 1 << 2
    EXECUTION_ERROR = 1 << 4
    COMMAND_ERROR = 1 << 5
    USER_REQUEST = 1 << 6
    POWER_ON = 1 << 7


class SerialPollBit(IntEnum):
    """Serial-poll register bit positions for the ``bit=`` argument.

    Bits 0 and 1 indicate no scan and no command execution in progress.
    ERROR, LIA_STATUS, and STANDARD_EVENT summarize enabled register events;
    MESSAGE_AVAILABLE indicates queued output and SERVICE_REQUEST indicates
    a service request. Bit 7 is unused.
    """

    NO_SCAN_IN_PROGRESS = 0
    NO_COMMAND_IN_PROGRESS = 1
    ERROR = 2
    LIA_STATUS = 3
    MESSAGE_AVAILABLE = 4
    STANDARD_EVENT = 5
    SERVICE_REQUEST = 6


class SerialPollFlag(IntFlag):
    """SerialPoll register masks for whole-byte values; combine with ``|``.

    Member meanings are documented in SerialPollBit. Each mask is 1 shifted
    by the corresponding bit position; NONE means no bits are set.
    """

    NONE = 0
    NO_SCAN_IN_PROGRESS = 1 << 0
    NO_COMMAND_IN_PROGRESS = 1 << 1
    ERROR = 1 << 2
    LIA_STATUS = 1 << 3
    MESSAGE_AVAILABLE = 1 << 4
    STANDARD_EVENT = 1 << 5
    SERVICE_REQUEST = 1 << 6


class ErrorBit(IntEnum):
    """Error-register bit positions for the ``bit=`` argument.

    BACKUP_ERROR reports failed battery backup; RAM_ERROR, ROM_ERROR, and
    DSP_ERROR report failed memory/processor tests. GPIB_ERROR reports an
    aborted fast transfer and MATH_ERROR an internal calculation error.
    Bits 0 and 3 are unused.
    """

    BACKUP_ERROR = 1
    RAM_ERROR = 2
    ROM_ERROR = 4
    GPIB_ERROR = 5
    DSP_ERROR = 6
    MATH_ERROR = 7


class ErrorFlag(IntFlag):
    """Error register masks for whole-byte values; combine with ``|``.

    Member meanings are documented in ErrorBit. Each mask is 1 shifted
    by the corresponding bit position; NONE means no bits are set.
    """

    NONE = 0
    BACKUP_ERROR = 1 << 1
    RAM_ERROR = 1 << 2
    ROM_ERROR = 1 << 4
    GPIB_ERROR = 1 << 5
    DSP_ERROR = 1 << 6
    MATH_ERROR = 1 << 7


class LiaStatusBit(IntEnum):
    """LIA-status register bit positions for the ``bit=`` argument.

    The first three bits report input/reserve, filter, and output overload.
    REFERENCE_UNLOCK reports lost reference lock; FREQUENCY_RANGE_CHANGED
    and TIME_CONSTANT_CHANGED report indirect setting changes; TRIGGER
    reports triggered data storage. Bit 7 is unused.
    """

    INPUT_OVERLOAD = 0
    FILTER_OVERLOAD = 1
    OUTPUT_OVERLOAD = 2
    REFERENCE_UNLOCK = 3
    FREQUENCY_RANGE_CHANGED = 4
    TIME_CONSTANT_CHANGED = 5
    TRIGGER = 6


class LiaStatusFlag(IntFlag):
    """LiaStatus register masks for whole-byte values; combine with ``|``.

    Member meanings are documented in LiaStatusBit. Each mask is 1 shifted
    by the corresponding bit position; NONE means no bits are set.
    """

    NONE = 0
    INPUT_OVERLOAD = 1 << 0
    FILTER_OVERLOAD = 1 << 1
    OUTPUT_OVERLOAD = 1 << 2
    REFERENCE_UNLOCK = 1 << 3
    FREQUENCY_RANGE_CHANGED = 1 << 4
    TIME_CONSTANT_CHANGED = 1 << 5
    TRIGGER = 1 << 6


_ENABLE_REGISTER_COMMANDS: Mapping[str, str] = MappingProxyType(
    {
        "standard_event": "*ESE",
        "serial_poll": "*SRE",
        "error": "ERRE",
        "lia_status": "LIAE",
    }
)

_STATUS_REGISTER_COMMANDS: Mapping[str, str] = MappingProxyType(
    {
        "standard_event": "*ESR?",
        "serial_poll": "*STB?",
        "error": "ERRS?",
        "lia_status": "LIAS?",
    }
)


# Positions and masks have distinct types to prevent confusing bit 2 with mask 4.
_REGISTER_BITS: Mapping[str, type[IntEnum]] = MappingProxyType(
    {
        "standard_event": StandardEventBit,
        "serial_poll": SerialPollBit,
        "error": ErrorBit,
        "lia_status": LiaStatusBit,
    }
)
_REGISTER_FLAGS: Mapping[str, type[IntFlag]] = MappingProxyType(
    {
        "standard_event": StandardEventFlag,
        "serial_poll": SerialPollFlag,
        "error": ErrorFlag,
        "lia_status": LiaStatusFlag,
    }
)


def _validate_enum(value: object, expected: type[Enum]) -> None:
    """Reject unrelated enums while retaining plain integer/string compatibility."""
    if issubclass(expected, (IntEnum, IntFlag)) and value is not None:
        _require_integer(value, expected.__name__)
    if isinstance(value, Enum) and not isinstance(value, expected):
        raise ValueError(
            f"Expected {expected.__name__}, received {type(value).__name__}."
        )


def _validate_register_bit(register: str, bit: object) -> None:
    """Validate an enum bit position against its register; integers remain valid."""
    _validate_enum(register, StatusRegister)
    if bit is not None:
        _require_integer(bit, "bit")
        if not isinstance(bit, Integral) or not 0 <= int(bit) <= 7:
            raise ValueError("bit must be in range 0 to 7.")
    if register in _REGISTER_BITS:
        _validate_enum(bit, _REGISTER_BITS[register])


def _validate_register_value(register: str, value: object, decimal: bool) -> None:
    """Validate masks for whole-byte writes and switch states for bit writes."""
    _validate_enum(register, StatusRegister)
    if not isinstance(decimal, bool):
        raise ValueError("decimal must be a bool.")
    _require_integer(value, "value")
    if not isinstance(value, Integral) or not 0 <= int(value) <= (
        255 if decimal else 1
    ):
        raise ValueError("value must be 0 to 255 for a mask, or 0/1 for a bit.")
    if register in _REGISTER_FLAGS:
        _validate_enum(value, _REGISTER_FLAGS[register] if decimal else SwitchState)


def _require_integer(value: object, name: str) -> None:
    """Validate integer protocol fields without truncating floats or accepting bools."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer.")


def _time_constant_seconds(code: int) -> float:
    """Convert the documented unit/value name for timing calculations."""
    unit, number = TimeConstant(code).name.split("_")
    return int(number) * {"us": 1e-6, "ms": 1e-3, "s": 1.0, "ks": 1e3}[unit]


def _full_scale(code: int, input_configuration: int) -> float:
    """Full-scale amplitude in V or A, from the sensitivity multiplier name."""
    text = Sensitivity(code).name[1:]
    suffix = text[-1] if text[-1].isalpha() else ""
    number = float(text[:-1] if suffix else text)
    return (
        number
        * {"": 1.0, "n": 1e-9, "u": 1e-6, "m": 1e-3}[suffix]
        * (1e-6 if input_configuration >= 2 else 1.0)
    )
