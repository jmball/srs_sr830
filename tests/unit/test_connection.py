"""Hardware-free connection lifecycle tests. Run with pytest."""

import pytest
import inspect
import struct
import warnings
import typing
from unittest.mock import Mock, PropertyMock, patch
import pyvisa
from pyvisa.constants import InterfaceType, SerialTermination
from sr830 import SR830
from virtual_sr830 import VirtualSR830


def test_serial_inference_and_initialization(connect, driver, manager, resource):

    def check_not_assigned(command):
        assert driver._instr is None

    resource.write.side_effect = check_not_assigned
    connect(baud_rate=19200, open_timeout=1000)
    manager.open_resource.assert_called_once_with("alias", open_timeout=1000)
    assert driver._instr is resource
    assert resource.read_termination == "\r"
    assert resource.write_termination == "\n"
    assert resource.baud_rate == 19200
    assert [c.args[0] for c in resource.write.call_args_list] == [
        "OUTX 0",
        "*ESE 255",
        "*SRE 255",
        "ERRE 255",
        "LIAE 255",
    ]


def test_gpib_inference(connect, manager, resource):
    manager.resource_info.return_value.interface_type = InterfaceType.gpib
    connect()
    assert resource.read_termination == "\n"
    resource.write.assert_any_call("OUTX 1")


def test_ambiguous_adapters_require_explicit_interface(
    connect, driver, manager, resource
):
    manager.resource_info.return_value.interface_type = InterfaceType.tcpip
    with pytest.raises(ValueError, match="Cannot infer"):
        connect()
    manager.open_resource.assert_not_called()
    for interface in (0, 1):
        connect(output_interface=interface)
        assert resource.read_termination == ("\r" if interface == 0 else "\n")
        driver.disconnect()


def test_explicit_interface_overrides_transport(connect, resource):
    connect(output_interface=1)
    resource.write.assert_any_call("OUTX 1")
    assert resource.read_termination == "\n"


def test_conflicts_are_rejected_before_opening(connect, manager):
    for kwargs in (
        {"read_termination": "\n"},
        {"write_termination": "x"},
        {"write_termination": None},
        {"output_interface": 2},
        {"output_interface": 1, "write_termination": None, "send_end": False},
    ):
        with pytest.raises((ValueError, TypeError)):
            connect(**kwargs)
    manager.open_resource.assert_not_called()


def test_valid_terminations_are_preserved(connect, driver, manager, resource):
    for interface, terminator in ((0, "\r"), (0, "\r\n"), (1, "\r\n"), (1, None)):
        manager.resource_info.return_value.interface_type = (
            InterfaceType.asrl if interface == 0 else InterfaceType.gpib
        )
        connect(output_interface=interface, write_termination=terminator)
        assert resource.write_termination == terminator
        driver.disconnect()


def test_each_initialization_command_failure_closes_resource(
    connect, driver, manager, resource
):
    for failed_command in range(5):
        resource.reset_mock()
        resource.write.side_effect = [None] * failed_command + [OSError("write failed")]
        with pytest.raises(OSError, match="write failed"):
            connect()
        resource.close.assert_called_once()
        assert driver._instr is None
        manager.close.assert_not_called()
    resource.write.side_effect = None
    connect()


def test_configuration_failure_closes_resource(connect, driver, resource):
    with patch.object(
        type(resource), "read_termination", new_callable=PropertyMock, create=True
    ) as attr:
        attr.side_effect = [None, OSError("configuration failed")]
        with pytest.raises(OSError, match="configuration failed"):
            connect()
    resource.close.assert_called_once()
    assert driver._instr is None


def test_unknown_attribute_closes_resource(connect, driver, resource):
    with pytest.raises(ValueError, match="not a valid"):
        connect(unknown_attribute=1)
    resource.close.assert_called_once()
    assert driver._instr is None


def test_open_failure_leaves_instance_disconnected(connect, driver, manager):
    manager.open_resource.side_effect = OSError("open failed")
    with pytest.raises(OSError, match="open failed"):
        connect()
    assert driver._instr is None
    manager.close.assert_not_called()


def test_close_error_does_not_mask_initialization_failure(connect, driver, resource):
    resource.write.side_effect = OSError("initialization failed")
    resource.close.side_effect = OSError("close failed")
    with pytest.raises(OSError, match="initialization failed"):
        connect()
    assert driver._instr is None


def test_reconnect_requires_disconnect(connect, driver, manager, resource):
    connect()
    with pytest.raises(RuntimeError, match="already connected"):
        connect()
    assert manager.open_resource.call_count == 1
    driver.disconnect()
    driver.disconnect()
    resource.close.assert_called_once()
    assert driver._instr is None
    manager.close.assert_not_called()
    connect()


def test_disconnect_closes_even_if_local_command_fails(connect, driver, resource):
    connect()
    resource.write.side_effect = OSError("local failed")
    with pytest.raises(OSError, match="local failed"):
        driver.disconnect()
    resource.close.assert_called_once()
    assert driver._instr is None
    driver.disconnect()


def test_disconnect_clears_state_if_close_fails(connect, driver, resource):
    connect()
    resource.close.side_effect = OSError("close failed")
    with pytest.raises(OSError, match="close failed"):
        driver.disconnect()
    assert driver._instr is None
    driver.disconnect()


def test_disconnect_tolerates_an_externally_closed_resource(connect, driver, resource):
    connect()
    resource.write.side_effect = pyvisa.errors.InvalidSession()
    driver.disconnect()
    resource.close.assert_called_once()
    assert driver._instr is None


def test_non_message_resource_is_closed(connect, driver, manager):
    resource = Mock()
    manager.open_resource.return_value = resource
    with pytest.raises(TypeError, match="message-based"):
        connect()
    resource.close.assert_called_once()
    assert driver._instr is None


def test_default_manager_is_used_but_not_closed(driver, manager):
    with patch("sr830.sr830.pyvisa.ResourceManager", return_value=manager):
        driver.connect("ASRL1::INSTR")
    manager.open_resource.assert_called_once_with("ASRL1::INSTR")
    driver.disconnect()
    manager.close.assert_not_called()


def test_context_manager_and_disconnected_io(connect, driver, resource):
    with driver:
        connect()
    resource.close.assert_called_once()
    with pytest.raises(RuntimeError, match="not connected"):
        driver.reference_frequency


def test_io_helpers_reject_disconnected_instances(connect, driver):
    operations = (
        lambda: driver._write("*RST"),
        lambda: driver._query("*IDN?"),
        lambda: driver._query_ascii_values("TRCA? 1,0,1"),
        lambda: driver._read_buffer_bytes("TRCB? 1,0,1", 4),
        lambda: setattr(driver, "output_interface", 1),
    )
    for connected_then_closed in (False, True):
        if connected_then_closed:
            connect()
            driver.disconnect()
        for operation in operations:
            with pytest.raises(RuntimeError, match="^Instrument is not connected\\.$"):
                operation()


def test_io_helpers_delegate_and_preserve_responses(connect, driver, resource):
    connect()
    resource.write.reset_mock()
    resource.write.return_value = 6
    assert driver._write("*RST") is None
    resource.write.assert_called_once_with("*RST")
    resource.query.return_value = "SR830,1234"
    assert driver._query("*IDN?") == "SR830,1234"
    resource.query.assert_called_once_with("*IDN?")
    resource.query_ascii_values.return_value = ["1.25", "-2.5", ""]
    assert driver._query_ascii_values("TRCA? 1,0,2") == ["1.25", "-2.5", ""]
    args, kwargs = resource.query_ascii_values.call_args
    assert args == ("TRCA? 1,0,2",)
    assert kwargs["container"] is list
    assert kwargs["converter"]("") == ""
    assert kwargs["converter"]("1.25") == "1.25"


def test_io_helpers_preserve_visa_errors(connect, driver, resource):
    connect()
    failure = pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_timeout)
    operations = (
        (resource.write, lambda: driver._write("*RST")),
        (resource.query, lambda: driver._query("*IDN?")),
        (
            resource.query_ascii_values,
            lambda: driver._query_ascii_values("TRCA? 1,0,1"),
        ),
    )
    for method, operation in operations:
        method.side_effect = failure
        with pytest.raises(pyvisa.errors.VisaIOError) as caught:
            operation()
        assert caught.value is failure
        method.side_effect = None


def test_ascii_buffer_uses_guarded_query_and_preserves_parsing(
    connect, driver, resource
):
    connect()
    resource.query.return_value = "0"
    resource.query_ascii_values.return_value = ["1.25", "-2.5", ""]
    assert driver.get_ascii_buffer_data(1, 0, 2) == (1.25, -2.5)
    assert resource.query_ascii_values.call_args.args == ("TRCA? 1,0,2",)


def test_virtual_connection_matches_api_and_preserves_settings():
    for name, interface in (("ASRL1::INSTR", 0), ("GPIB0::14::INSTR", 1)):
        virtual = VirtualSR830()
        virtual.reference_frequency = 1234.0
        virtual.connect(name)
        assert virtual.output_interface == interface
        assert virtual.reference_frequency == 1234.0
        with pytest.raises(RuntimeError):
            virtual.connect(name)
        virtual.disconnect()
        virtual.disconnect()
        assert virtual.local_mode == 0
    virtual = VirtualSR830()
    with pytest.raises(ValueError):
        virtual.connect("TCPIP0::example.invalid::1234::SOCKET")
    virtual.connect("TCPIP0::example.invalid::1234::SOCKET", output_interface=1)
    virtual.disconnect()
    with pytest.raises(ValueError):
        virtual.connect("ASRL1::INSTR", read_termination="\n")


def test_tcpip_adapters_require_command_terminator(connect, manager):
    manager.resource_info.return_value.interface_type = InterfaceType.tcpip
    with pytest.raises(ValueError):
        connect(output_interface=1, write_termination=None)
    manager.open_resource.assert_not_called()


def test_local_mode_is_an_explicit_caller_setting(connect, driver, resource):
    connect()
    assert not any(
        (c.args[0].startswith("LOCL") for c in resource.write.call_args_list)
    )
    driver.local_mode = 2
    resource.write.assert_called_with("LOCL 2")
    driver.local_mode = 1
    resource.write.assert_called_with("LOCL 1")
    for mode in (0, 1, 2):
        virtual = VirtualSR830()
        virtual.local_mode = mode
        virtual.connect("ASRL1::INSTR")
        assert virtual.local_mode == mode


def test_getters_query_responses(connect, driver, resource):
    connect()
    resource.query.side_effect = ["2,1", "1"]
    assert driver.get_display(1) == (2, 1)
    assert driver.gpib_override_remote == 1
    assert [c.args[0] for c in resource.query.call_args_list] == ["DDEF? 1", "OVRM?"]


def test_set_enable_register_requires_bit_for_binary_values(connect, driver, resource):
    connect()
    with pytest.raises(ValueError):
        driver.set_enable_register("error", 1, decimal=False)
    driver.set_enable_register("error", 1, decimal=False, bit=3)
    resource.write.assert_any_call("ERRE 3,1")


def test_binary_buffers_ignore_text_terminators_and_restore_framing(
    connect, driver, resource
):
    connect()
    original_end = resource.end_input
    raw = bytes([13, 10, 128, 63])

    def read(size, **kwargs):
        assert size == 4
        assert kwargs == {"break_on_termchar": False}
        assert resource.read_termination is None
        assert resource.end_input == SerialTermination.none
        return raw

    resource.read_bytes.side_effect = read
    resource.query.side_effect = ["0", "0"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert driver.get_binary_buffer_data(1, 0, 1) == struct.unpack("<f", raw)
    resource.write.assert_any_call("TRCB? 1,0,1")
    assert resource.read_termination == "\r"
    assert resource.end_input == original_end
    resource.read_bytes.side_effect = None
    resource.read_bytes.return_value = struct.pack("<hh", 10, 124)
    resource.query.side_effect = ["0", "0"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert driver.get_non_norm_buffer_data(1, 0, 1) == (10.0,)
    resource.write.assert_any_call("TRCL? 1,0,1")


def test_binary_read_failure_restores_text_framing(connect, driver, resource):
    connect()
    original_end = resource.end_input
    resource.query.side_effect = ["1", "0"]
    resource.read_bytes.side_effect = OSError("read failed")
    with pytest.raises(OSError, match="read failed"):
        driver.get_binary_buffer_data(1, 0, 1)
    assert resource.read_termination == "\r"
    assert resource.end_input == original_end


def test_all_driver_methods_have_resolvable_annotations():
    for cls in (SR830, VirtualSR830):
        assert inspect.signature(cls.connect) == inspect.signature(SR830.connect)
        for name, member in vars(cls).items():
            functions = [member] if inspect.isfunction(member) else []
            if isinstance(member, property):
                functions = [f for f in (member.fget, member.fset) if f is not None]
            for function in functions:
                hints = typing.get_type_hints(function)
                assert "return" in hints, name
                for parameter in inspect.signature(function).parameters:
                    if parameter != "self":
                        assert parameter in hints, name
