"""Enum-specific API behavior: serialization, cross-package inputs, and type safety."""

from unittest.mock import patch

import pytest

from sr830 import settings
from virtual_sr830 import Sensitivity


def test_virtual_package_enum_is_accepted_by_hardware_driver(mock_instrument, resource):
    mock_instrument.sensitivity = Sensitivity.x1u
    resource.write.assert_called_once_with("SENS 8")


def test_snap_serializes_codes_independently_of_enum_string_format(
    mock_instrument, resource
):
    # IntEnum.__str__ differs across supported Python versions. Wire codes must not.
    with patch.object(
        settings.MeasurementParameter, "__str__", lambda member: member.name
    ):
        resource.query.return_value = "0.003,1000"
        values = mock_instrument.measure_multiple(
            [
                settings.MeasurementParameter.X,
                settings.MeasurementParameter.REFERENCE_FREQUENCY,
            ]
        )
        assert tuple(values) == (0.003, 1000.0)
    resource.query.assert_called_once_with("SNAP? 1,9")


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(
            lambda d: setattr(d, "sensitivity", settings.ReferenceSource.INTERNAL),
            id="setting",
        ),
        pytest.param(
            lambda d: d.set_display(1, settings.Channel2Display.PHASE),
            id="display-channel",
        ),
        pytest.param(
            lambda d: d.set_display(
                2, settings.Channel2Display.Y, settings.Channel1Ratio.AUX_IN_1
            ),
            id="ratio-channel",
        ),
        pytest.param(
            lambda d: d.read_display(settings.AuxiliaryChannel.AUX1),
            id="channel-selector",
        ),
        pytest.param(
            lambda d: d.measure(settings.OutputParameter.X), id="measurement-selector"
        ),
        pytest.param(
            lambda d: d.measure_multiple(
                [settings.MeasurementParameter.X, settings.Channel.CH2]
            ),
            id="snap-selector",
        ),
        pytest.param(
            lambda d: d.get_status_byte("error", settings.SerialPollBit.ERROR),
            id="register-bit-type",
        ),
        pytest.param(
            lambda d: d.get_enable_register("error", settings.ErrorFlag.RAM_ERROR),
            id="mask-as-bit",
        ),
        pytest.param(
            lambda d: d.set_enable_register("error", settings.ErrorBit.RAM_ERROR),
            id="bit-as-mask",
        ),
        pytest.param(
            lambda d: d.set_enable_register("error", settings.SerialPollFlag.ERROR),
            id="register-mask-type",
        ),
        pytest.param(
            lambda d: d.set_enable_register(
                "error",
                settings.ErrorFlag.RAM_ERROR,
                decimal=False,
                bit=settings.ErrorBit.RAM_ERROR,
            ),
            id="mask-as-switch",
        ),
    ],
)
def test_unrelated_enums_are_rejected_even_when_codes_are_valid(
    mock_instrument, resource, operation
):
    with pytest.raises(ValueError):
        operation(mock_instrument)
    resource.write.assert_not_called()
    resource.query.assert_not_called()


@pytest.mark.parametrize(
    "register,mask,bit,expected_write,expected_status_query",
    [
        (
            "standard_event",
            settings.StandardEventFlag.EXECUTION_ERROR,
            settings.StandardEventBit.EXECUTION_ERROR,
            "*ESE 16",
            "*ESR? 4",
        ),
        (
            "serial_poll",
            settings.SerialPollFlag.ERROR,
            settings.SerialPollBit.ERROR,
            "*SRE 4",
            "*STB? 2",
        ),
        (
            "error",
            settings.ErrorFlag.RAM_ERROR,
            settings.ErrorBit.RAM_ERROR,
            "ERRE 4",
            "ERRS? 2",
        ),
        (
            "lia_status",
            settings.LiaStatusFlag.OUTPUT_OVERLOAD,
            settings.LiaStatusBit.OUTPUT_OVERLOAD,
            "LIAE 4",
            "LIAS? 2",
        ),
    ],
)
def test_register_wire_contract(
    mock_instrument,
    resource,
    register,
    mask,
    bit,
    expected_write,
    expected_status_query,
):
    mock_instrument.set_enable_register(register, mask)
    resource.write.assert_called_with(expected_write)
    command = expected_write.split()[0]
    position = expected_status_query.split()[1]
    mock_instrument.set_enable_register(
        register, settings.SwitchState.ON, decimal=False, bit=bit
    )
    resource.write.assert_called_with(f"{command} {position},1")
    resource.query.return_value = "1"
    assert mock_instrument.get_enable_register(register, bit) == 1
    resource.query.assert_called_with(f"{command}? {position}")
    assert mock_instrument.get_status_byte(register, bit) == 1
    resource.query.assert_called_with(expected_status_query)


def test_enable_all_status_bytes_writes_all_four_registers(mock_instrument, resource):
    mock_instrument.enable_all_status_bytes()
    assert [call.args[0] for call in resource.write.call_args_list] == [
        "*ESE 255",
        "*SRE 255",
        "ERRE 255",
        "LIAE 255",
    ]
