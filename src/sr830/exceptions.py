"""Instrument-reported faults, distinct from VISA transport failures."""

from collections.abc import Callable, Mapping
from types import MappingProxyType

from .settings import ErrorFlag, LiaStatusFlag, StandardEventFlag


class InstrumentError(RuntimeError):
    """Latched SR830 faults detected after an operation.

    Attributes
    ----------
    operation : str
        Operation after which the faults were detected, not necessarily their cause.
    errors : tuple of str
        Decoded fault descriptions.
    registers : Mapping[str, int]
        Raw register values read while checking. Reading event registers clears them.
    """

    def __init__(
        self, operation: str, errors: tuple[str, ...], registers: Mapping[str, int]
    ) -> None:
        self.operation = operation
        self.errors = errors
        self.registers = MappingProxyType(dict(registers))
        super().__init__(
            f"Instrument errors detected after {operation}: {'; '.join(errors)}"
        )


_FAULTS = {
    "*ESR?": (
        (StandardEventFlag.INPUT_QUEUE_OVERFLOW, "Input queue overflow"),
        (StandardEventFlag.OUTPUT_QUEUE_OVERFLOW, "Output queue overflow"),
        (
            StandardEventFlag.EXECUTION_ERROR,
            "Command cannot execute/parameter out of range",
        ),
        (StandardEventFlag.COMMAND_ERROR, "Received illegal command"),
    ),
    "ERRS?": (
        (ErrorFlag.BACKUP_ERROR, "Battery backup has failed"),
        (ErrorFlag.RAM_ERROR, "RAM memory test found error"),
        (ErrorFlag.ROM_ERROR, "ROM memory test found error"),
        (ErrorFlag.GPIB_ERROR, "GPIB fast data transfer mode aborted"),
        (ErrorFlag.DSP_ERROR, "DSP test found error"),
        (ErrorFlag.MATH_ERROR, "Internal math error"),
    ),
    "LIAS?": (
        (LiaStatusFlag.INPUT_OVERLOAD, "Input or amplifier overload"),
        (LiaStatusFlag.FILTER_OVERLOAD, "Time constant filter overload"),
        (LiaStatusFlag.OUTPUT_OVERLOAD, "Output overload"),
        (LiaStatusFlag.REFERENCE_UNLOCK, "Reference unlock detected"),
    ),
}


def _check_registers(
    query: Callable[[str], str], commands: tuple[str, ...], operation: str
) -> None:
    registers: dict[str, int] = {}
    errors: list[str] = []
    try:
        for command in commands:
            value = int(query(command))
            if not 0 <= value <= 255:
                raise OSError(f"Invalid status response to {command}: {value}")
            registers[command] = value
            errors.extend(message for flag, message in _FAULTS[command] if value & flag)
    except Exception as exc:
        # Do not lose a confirmed fault if a later diagnostic query fails.
        if errors:
            raise InstrumentError(operation, tuple(errors), registers) from exc
        raise
    if errors:
        raise InstrumentError(operation, tuple(errors), registers)
