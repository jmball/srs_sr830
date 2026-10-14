"""Shared SR830 command codes and immutable setting tables.

Tuple indices are instrument command codes. Sensitivity values are in volts for
voltage inputs and microamps for current inputs; time constants are in seconds.
The sample rate table is in Hz, with the final entry selecting triggered sampling.
"""
from collections.abc import Mapping
from enum import Enum, IntEnum, IntFlag
from types import MappingProxyType
from typing import ClassVar


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
    """Voltage or current input configuration (ISRC)."""

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
    """Dynamic reserve mode (RMOD)."""

    HIGH_RESERVE = 0
    NORMAL = 1
    LOW_NOISE = 2


class SynchronousFilter(IntEnum):
    """Synchronous filter state (SYNC)."""

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
    """Display or X (channel 1)/Y (channel 2) output (FPOP)."""

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
    """GPIB fast transfer mode (FAST)."""

    OFF = 0
    DOS = 1
    WINDOWS = 2


class LocalMode(IntEnum):
    """Local, remote, or front-panel lockout mode (LOCL)."""

    LOCAL = 0
    REMOTE = 1
    LOCAL_LOCKOUT = 2


class GpibOverrideRemote(IntEnum):
    """GPIB remote override state (OVRM)."""

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
    """OFLT codes named by time unit and number, e.g. ``ms_100`` (100 ms)."""

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
    """OFSL codes named by slope in dB per octave."""

    DB_6 = 0
    DB_12 = 1
    DB_18 = 2
    DB_24 = 3


class OutputExpansion(IntEnum):
    """OEXP codes: code 0 means unity gain, not zero gain."""

    x_1 = 0
    x_10 = 1
    x_100 = 2


class SampleRate(IntEnum):
    """SRAT codes named by frequency unit and number, or external trigger mode."""

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
    """StandardEvent register bit positions for the ``bit=`` argument."""

    INPUT_QUEUE_OVERFLOW = 0
    OUTPUT_QUEUE_OVERFLOW = 2
    EXECUTION_ERROR = 4
    COMMAND_ERROR = 5
    USER_REQUEST = 6
    POWER_ON = 7


class StandardEventFlag(IntFlag):
    """StandardEvent register masks for whole-byte values; combine with ``|``."""

    NONE = 0
    INPUT_QUEUE_OVERFLOW = 1 << 0
    OUTPUT_QUEUE_OVERFLOW = 1 << 2
    EXECUTION_ERROR = 1 << 4
    COMMAND_ERROR = 1 << 5
    USER_REQUEST = 1 << 6
    POWER_ON = 1 << 7


class SerialPollBit(IntEnum):
    """SerialPoll register bit positions for the ``bit=`` argument."""

    NO_SCAN_IN_PROGRESS = 0
    NO_COMMAND_IN_PROGRESS = 1
    ERROR = 2
    LIA_STATUS = 3
    MESSAGE_AVAILABLE = 4
    STANDARD_EVENT = 5
    SERVICE_REQUEST = 6


class SerialPollFlag(IntFlag):
    """SerialPoll register masks for whole-byte values; combine with ``|``."""

    NONE = 0
    NO_SCAN_IN_PROGRESS = 1 << 0
    NO_COMMAND_IN_PROGRESS = 1 << 1
    ERROR = 1 << 2
    LIA_STATUS = 1 << 3
    MESSAGE_AVAILABLE = 1 << 4
    STANDARD_EVENT = 1 << 5
    SERVICE_REQUEST = 1 << 6


class ErrorBit(IntEnum):
    """Error register bit positions for the ``bit=`` argument."""

    BACKUP_ERROR = 1
    RAM_ERROR = 2
    ROM_ERROR = 4
    GPIB_ERROR = 5
    DSP_ERROR = 6
    MATH_ERROR = 7


class ErrorFlag(IntFlag):
    """Error register masks for whole-byte values; combine with ``|``."""

    NONE = 0
    BACKUP_ERROR = 1 << 1
    RAM_ERROR = 1 << 2
    ROM_ERROR = 1 << 4
    GPIB_ERROR = 1 << 5
    DSP_ERROR = 1 << 6
    MATH_ERROR = 1 << 7


class LiaStatusBit(IntEnum):
    """LiaStatus register bit positions for the ``bit=`` argument."""

    INPUT_OVERLOAD = 0
    FILTER_OVERLOAD = 1
    OUTPUT_OVERLOAD = 2
    REFERENCE_UNLOCK = 3
    FREQUENCY_RANGE_CHANGED = 4
    TIME_CONSTANT_CHANGED = 5
    TRIGGER = 6


class LiaStatusFlag(IntFlag):
    """LiaStatus register masks for whole-byte values; combine with ``|``."""

    NONE = 0
    INPUT_OVERLOAD = 1 << 0
    FILTER_OVERLOAD = 1 << 1
    OUTPUT_OVERLOAD = 1 << 2
    REFERENCE_UNLOCK = 1 << 3
    FREQUENCY_RANGE_CHANGED = 1 << 4
    TIME_CONSTANT_CHANGED = 1 << 5
    TRIGGER = 1 << 6


# Positions and masks have distinct types to prevent confusing bit 2 with mask 4.
_REGISTER_BITS: Mapping[str, type[IntEnum]] = MappingProxyType({
    "standard_event": StandardEventBit,
    "serial_poll": SerialPollBit,
    "error": ErrorBit,
    "lia_status": LiaStatusBit,
})
_REGISTER_FLAGS: Mapping[str, type[IntFlag]] = MappingProxyType({
    "standard_event": StandardEventFlag,
    "serial_poll": SerialPollFlag,
    "error": ErrorFlag,
    "lia_status": LiaStatusFlag,
})


def _validate_enum(value: object, expected: type[Enum]) -> None:
    """Reject unrelated enums while retaining plain integer/string compatibility."""
    if isinstance(value, Enum) and not isinstance(value, expected):
        raise ValueError(f"Expected {expected.__name__}, received {type(value).__name__}.")


def _validate_register_bit(register: str, bit: object) -> None:
    """Validate an enum bit position against its register; integers remain valid."""
    _validate_enum(register, StatusRegister)
    if register in _REGISTER_BITS:
        _validate_enum(bit, _REGISTER_BITS[register])


def _validate_register_value(register: str, value: object, decimal: bool) -> None:
    """Validate masks for whole-byte writes and switch states for bit writes."""
    _validate_enum(register, StatusRegister)
    if register in _REGISTER_FLAGS:
        _validate_enum(value, _REGISTER_FLAGS[register] if decimal else SwitchState)


class _Settings:
    """Model constants inherited by the hardware and virtual drivers."""

    # Public tables retain the original attribute names and tuple values.

    reference_sources: ClassVar[tuple[str, ...]] = ("external", "internal")

    triggers: ClassVar[tuple[str, ...]] = (
        'zero crossing',
        'TTL rising egde',
        'TTL falling edge',
    )

    input_configurations: ClassVar[tuple[str, ...]] = ("A", "A-B", "I (1 MOhm)", "I (100 MOhm)")

    groundings: ClassVar[tuple[str, ...]] = ("Float", "Ground")

    input_couplings: ClassVar[tuple[str, ...]] = ("AC", "DC")

    input_line_notch_filter_statuses: ClassVar[tuple[str, ...]] = (
        "no filters",
        "Line notch in",
        "2 x Line notch in",
        "Both notch filters in",
    )

    # Values are V for voltage inputs and microamps for current inputs.
    sensitivities: ClassVar[tuple[float, ...]] = (
        2e-9,
        5e-9,
        10e-9,
        20e-9,
        50e-9,
        100e-9,
        200e-9,
        500e-9,
        1e-6,
        2e-6,
        5e-6,
        10e-6,
        20e-6,
        50e-6,
        100e-6,
        200e-6,
        500e-6,
        1e-3,
        2e-3,
        5e-3,
        10e-3,
        20e-3,
        50e-3,
        100e-3,
        200e-3,
        500e-3,
        1.0,
    )

    reserve_modes: ClassVar[tuple[str, ...]] = ("High reserve", "Normal", "Low noise")

    # Values are seconds; setters still take integer table indices.
    time_constants: ClassVar[tuple[float, ...]] = (
        10e-6,
        30e-6,
        100e-6,
        300e-6,
        1e-3,
        3e-3,
        10e-3,
        30e-3,
        100e-3,
        300e-3,
        1.0,
        3.0,
        10.0,
        30.0,
        100.0,
        300.0,
        1e3,
        3e3,
        10e3,
        30e3,
    )

    low_pass_filter_slopes: ClassVar[tuple[int, ...]] = (6, 12, 18, 24)

    synchronous_filter_statuses: ClassVar[tuple[str, ...]] = ("Off", "below 200 Hz")

    display_ch1: ClassVar[tuple[str, ...]] = ("X", "R", "X Noise", "Aux In 1", "Aux In 2")

    display_ch2: ClassVar[tuple[str, ...]] = ("Y", "Phase", "Y Noise", "Aux In 3", "Aux In 4")

    ratio_ch1: ClassVar[tuple[str, ...]] = ("none", "Aux In 1", "Aux In 2")

    ratio_ch2: ClassVar[tuple[str, ...]] = ("none", "Aux In 3", "Aux In 4")

    front_panel_output_sources_ch1: ClassVar[tuple[str, ...]] = ("CH1 display", "X")

    front_panel_output_sources_ch2: ClassVar[tuple[str, ...]] = ("CH2 display", "Y")

    expands: ClassVar[tuple[int, ...]] = (0, 10, 100)

    output_interfaces: ClassVar[tuple[str, ...]] = ("RS232", "GPIB")

    key_click_states: ClassVar[tuple[str, ...]] = ("Off", "On")

    alarm_statuses: ClassVar[tuple[str, ...]] = ("Off", "On")

    sample_rates: ClassVar[tuple[float | str, ...]] = (
        62.5e-3,
        125e-3,
        250e-3,
        500e-3,
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
        256,
        512,
        "Trigger",
    )

    end_of_buffer_modes: ClassVar[tuple[str, ...]] = ("1 Shot", "Loop")

    trigger_start_modes: ClassVar[tuple[str, ...]] = ("Off", "Start scan")

    data_transfer_modes: ClassVar[tuple[str, ...]] = ("Off", "On (DOS)", "On (Windows)")

    local_modes: ClassVar[tuple[str, ...]] = ("Local", "Remote", "Local lockout")

    gpib_override_remote_conditions: ClassVar[tuple[str, ...]] = ("No", "Yes")

    # --- private class variables ---

    _enable_register_cmd_dict: ClassVar[Mapping[str, str]] = MappingProxyType({
        "standard_event": "*ESE",
        "serial_poll": "*SRE",
        "error": "ERRE",
        "lia_status": "LIAE",
    })

    _status_byte_cmd_dict: ClassVar[Mapping[str, str]] = MappingProxyType({
        "standard_event": "*ESR?",
        "serial_poll": "*STB?",
        "error": "ERRS?",
        "lia_status": "LIAS?",
    })

    # Meaning of status bits. Outer tuple indices are bit numbers.
    # Inner tuple indices select the description of an event or state.
    _serial_poll_status_bit_names: ClassVar[tuple[str, ...]] = (
        "SCN",
        "IFC",
        "ERR",
        "LIA",
        "MAV",
        "ESB",
        "SRQ",
        "Unused",
    )
    _serial_poll_status_byte: ClassVar[tuple[tuple[str, str], ...]] = (
        ('', 'No scan in progress'),
        ('', 'No command execution in progress'),
        ('', 'An enabled bit in error status byte has been set'),
        ('', 'An enabled bit in LIA status byte has been set'),
        ('', 'Interface output buffer is non-empty'),
        ('', 'An enabled bit in standard status byte has been set'),
        ('', 'A service request has occured'),
        ('', ''),
    )

    _standard_event_status_bit_names: ClassVar[tuple[str, ...]] = (
        "INP",
        "Unused",
        "QRY",
        "Unused",
        "EXE",
        "CMD",
        "URQ",
        "PON",
    )
    _standard_event_status_byte: ClassVar[tuple[tuple[str, str], ...]] = (
        ('', 'Input queue overflow'),
        ('', ''),
        ('', 'Output queue overflow'),
        ('', ''),
        ('', 'Command cannot execute/parameter out of range'),
        ('', 'Received illegal command'),
        ('', 'Key pressed/knob rotated'),
        ('', 'Power-on'),
    )

    _lia_status_bit_names: ClassVar[tuple[str, ...]] = (
        "INPUT/RESRV",
        "FILTR",
        "OUTPUT",
        "UNLK",
        "RANGE",
        "TC",
        "TRIG",
        "Unused",
    )
    _lia_status_byte: ClassVar[tuple[tuple[str, str], ...]] = (
        ('', 'Input or amplifier overload'),
        ('', 'Time constant filter overload'),
        ('', 'Output overload'),
        ('', 'Reference unlock detected'),
        ('', 'Detection frequency switched range'),
        ('', 'Time constant changed indirectly'),
        ('', 'Data storage triggered'),
        ('', ''),
    )

    _error_status_bit_names: ClassVar[tuple[str, ...]] = (
        "Unused",
        "Backup error",
        "RAM error",
        "Unused",
        "ROM error",
        "GPIB error",
        "DSP error",
        "Math error",
    )
    _error_status_byte: ClassVar[tuple[tuple[str, str], ...]] = (
        ('', ''),
        ('', 'Battery backup has failed'),
        ('', 'RAM memory test found error'),
        ('', ''),
        ('', 'ROM memory test found error'),
        ('', 'GPIB fast data transfer mode aborted'),
        ('', 'DSP test found error'),
        ('', 'Internal math error'),
    )

