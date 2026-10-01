"""Connection settings shared by the hardware and virtual instruments."""

from typing import Any

from pyvisa.constants import InterfaceType

from .settings import OutputInterface


def resolve_output_interface(
    interface_type: InterfaceType, output_interface: int | None
) -> int:
    """Infer direct VISA interfaces, requiring an override for adapters."""
    if output_interface is not None:
        if output_interface not in (OutputInterface.RS232, OutputInterface.GPIB):
            raise ValueError("output_interface must be 0 (RS232) or 1 (GPIB).")
        return int(output_interface)
    if interface_type == InterfaceType.asrl:
        return int(OutputInterface.RS232)
    if interface_type == InterfaceType.gpib:
        return int(OutputInterface.GPIB)
    raise ValueError(
        "Cannot infer the SR830 interface from this VISA resource. "
        "Specify output_interface=0 (RS232) or output_interface=1 (GPIB) "
        "for the adapter's instrument-side interface."
    )


def connection_kwargs(
    output_interface: int,
    resource_kwargs: dict[str, Any],
    *,
    interface_type: InterfaceType,
) -> dict[str, Any]:
    """Validate framing and supply protocol defaults without overwriting callers."""
    kwargs = resource_kwargs.copy()
    read_termination = "\r" if output_interface == 0 else "\n"
    if "read_termination" in kwargs and kwargs["read_termination"] != read_termination:
        raise ValueError(f"read_termination must be {read_termination!r}.")
    kwargs.setdefault("read_termination", read_termination)
    kwargs.setdefault("write_termination", "\n")
    allowed = ("\r", "\n", "\r\n") if output_interface == 0 else ("\n", "\r\n")
    termination = kwargs["write_termination"]
    # GPIB also permits command termination by EOI alone.
    if termination not in allowed and not (
        output_interface == 1
        and interface_type == InterfaceType.gpib
        and termination in (None, "")
        and kwargs.get("send_end", True) is True
    ):
        raise ValueError("write_termination conflicts with the SR830 command protocol.")
    return kwargs
