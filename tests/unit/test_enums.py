"""Named codes, selectors, and register bits without real hardware."""

import pytest
from enum import IntEnum, IntFlag
import inspect
import struct
import typing
from unittest.mock import patch
import sr830
import sr830.settings as settings
import virtual_sr830
from tests.cases import NUMERIC_PROPERTIES

REGISTER_TYPES = (
    (
        settings.StatusRegister.STANDARD_EVENT,
        settings.StandardEventBit,
        settings.StandardEventFlag,
        "*ESE",
        "*ESR?",
    ),
    (
        settings.StatusRegister.SERIAL_POLL,
        settings.SerialPollBit,
        settings.SerialPollFlag,
        "*SRE",
        "*STB?",
    ),
    (
        settings.StatusRegister.ERROR,
        settings.ErrorBit,
        settings.ErrorFlag,
        "ERRE",
        "ERRS?",
    ),
    (
        settings.StatusRegister.LIA_STATUS,
        settings.LiaStatusBit,
        settings.LiaStatusFlag,
        "LIAE",
        "LIAS?",
    ),
)


def test_all_enums_are_exported_by_both_packages():
    for name, enum in vars(settings).items():
        if (
            inspect.isclass(enum)
            and issubclass(enum, (IntEnum, IntFlag, settings.StatusRegister))
            and (enum.__module__ == settings.__name__)
        ):
            assert getattr(sr830, name) is enum
            assert getattr(virtual_sr830, name) is enum


def test_numeric_names_and_instrument_codes():
    assert settings.Sensitivity.x1u == 8
    assert settings.Sensitivity.x200m == 24
    assert settings.Sensitivity.x1 == 26
    assert settings.Sensitivity(26) is settings.Sensitivity.x1
    assert settings.Sensitivity.__members__["x1"] is settings.Sensitivity.x1
    for enum, count in (
        (settings.Sensitivity, 27),
        (settings.TimeConstant, 20),
        (settings.LowPassFilterSlope, 4),
        (settings.SampleRate, 15),
    ):
        assert [int(member) for member in enum] == list(range(count))
    assert settings.Sensitivity.x2n == 0
    assert settings.TimeConstant.us_10 == 0
    assert settings.TimeConstant.ms_100 == 8
    assert settings.TimeConstant.ks_30 == 19
    assert [member.name for member in settings.LowPassFilterSlope] == [
        "dB_6",
        "dB_12",
        "dB_18",
        "dB_24",
    ]
    assert settings.SampleRate.mHz_62_5 == 0
    assert settings.SampleRate.Hz_512 == 13
    assert settings.SampleRate.TRIGGER == 14
    assert [member.name for member in settings.OutputExpansion] == ["x1", "x10", "x100"]


def test_numeric_invalid_codes_and_wrong_enum_classes(
    mock_instrument, resource, virtual
):
    for driver in (mock_instrument, virtual):
        for name, enum, command in NUMERIC_PROPERTIES:
            for value in (-1, len(enum), settings.ReferenceSource.INTERNAL):
                with pytest.raises(ValueError):
                    setattr(driver, name, value)
        with pytest.raises(ValueError, match="ReferenceSource"):
            driver.reference_source = settings.LocalMode.REMOTE
    resource.write.assert_not_called()


def test_display_enums_are_checked_against_channel(mock_instrument, resource, virtual):
    for driver in (mock_instrument, virtual):
        for channel, displays, ratios in (
            (settings.Channel.CH1, settings.Channel1Display, settings.Channel1Ratio),
            (settings.Channel.CH2, settings.Channel2Display, settings.Channel2Ratio),
        ):
            for display in displays:
                for ratio in ratios:
                    driver.set_display(channel, display, ratio)
                    if driver is mock_instrument:
                        resource.write.assert_called_with(
                            f"DDEF {int(channel)}, {int(display)}, {int(ratio)}"
                        )
                        resource.query.return_value = f"{int(display)},{int(ratio)}"
                    assert driver.get_display(channel) == (int(display), int(ratio))
        with pytest.raises(ValueError):
            driver.set_display(settings.Channel.CH1, settings.Channel2Display.PHASE)
        with pytest.raises(ValueError):
            driver.set_display(
                settings.Channel.CH2,
                settings.Channel2Display.Y,
                settings.Channel1Ratio.AUX_IN_1,
            )


def test_output_expansion_and_parameter_codes(mock_instrument, resource, virtual):
    for parameter in settings.OutputParameter:
        for expand in settings.OutputExpansion:
            for driver in (mock_instrument, virtual):
                driver.set_output_offset_expand(parameter, 12.5, expand)
                if driver is mock_instrument:
                    resource.write.assert_called_with(
                        f"OEXP {int(parameter)}, 12.5, {int(expand)}"
                    )
                    resource.query.return_value = f"12.5,{int(expand)}"
                assert driver.get_output_offset_expand(parameter) == (12.5, int(expand))
                assert type(driver.get_output_offset_expand(parameter)[1]) is int
                driver.auto_offset(parameter)
            resource.write.assert_called_with(f"AOFF {int(parameter)}")
    assert [int(x) for x in settings.OutputExpansion] == [0, 1, 2]
    for driver in (mock_instrument, virtual):
        for operation in (driver.get_output_offset_expand, driver.auto_offset):
            with pytest.raises(ValueError):
                operation(0)


def test_buffer_readers_accept_channel_enums_and_reject_zero(
    mock_instrument, resource, virtual
):
    for driver in (mock_instrument, virtual):
        for method in (
            driver.get_ascii_buffer_data,
            driver.get_binary_buffer_data,
            driver.get_non_norm_buffer_data,
        ):
            with pytest.raises(ValueError):
                method(0, 0, 1)
    resource.query.side_effect = ["0", "1", "0", "1"]
    resource.query_ascii_values.return_value = ["1.5", ""]
    for channel in settings.Channel:
        assert mock_instrument.get_ascii_buffer_data(channel, 0, 1) == (1.5,)
        assert resource.query_ascii_values.call_args.args == (
            f"TRCA? {int(channel)},0,1",
        )


def test_loop_buffer_readers_use_enum_modes_without_legacy_tables(
    mock_instrument, resource
):
    readers = (
        (mock_instrument.get_ascii_buffer_data, "TRCA?", None),
        (mock_instrument.get_binary_buffer_data, "TRCB?", struct.pack("<f", 1.25)),
        (
            mock_instrument.get_non_norm_buffer_data,
            "TRCL?",
            struct.pack("<hh", 10, 124),
        ),
    )
    resource.read_termination = "\n"
    for reader, command, raw in readers:
        resource.write.reset_mock()
        resource.query.side_effect = ["1", "1"] if raw is None else ["1", "1", "1"]
        resource.query_ascii_values.return_value = ["1.25", ""]
        resource.read_bytes.return_value = raw
        result = reader(settings.Channel.CH2, 0, 1)
        assert result == ((10.0,) if command == "TRCL?" else (1.25,))
        commands = [call.args[0] for call in resource.write.call_args_list]
        assert commands[0] == "PAUS"
        assert "SEND 1" not in commands
        assert "STRT" not in commands
        if raw is not None:
            assert f"{command} 2,0,1" in commands


def test_measurement_selectors_and_integer_serialization(
    mock_instrument, resource, virtual
):
    resource.query.return_value = "1.25"
    for parameter in settings.MeasurementParameter:
        for driver in (mock_instrument, virtual):
            if int(parameter) <= 4:
                driver.measure(parameter)
            else:
                with pytest.raises(ValueError):
                    driver.measure(parameter)
    with patch.object(
        settings.MeasurementParameter,
        "__str__",
        lambda member: f"MeasurementParameter.{member.name}",
    ):
        assert str(settings.MeasurementParameter.X) == "MeasurementParameter.X"
        for second in list(settings.MeasurementParameter)[1:]:
            resource.query.return_value = "1.0,2.0"
            assert tuple(
                mock_instrument.measure_multiple(
                    [settings.MeasurementParameter.X, second]
                )
            ) == (1.0, 2.0)
            resource.query.assert_called_with(f"SNAP? 1,{int(second)}")
    for driver in (mock_instrument, virtual):
        with pytest.raises(ValueError):
            driver.measure(settings.OutputParameter.X)
        with pytest.raises(ValueError):
            driver.measure_multiple(
                [settings.MeasurementParameter.X, settings.Channel.CH2]
            )


def test_channel_and_auxiliary_selectors(mock_instrument, resource, virtual):
    resource.query.return_value = "1"
    for channel in settings.Channel:
        for driver in (mock_instrument, virtual):
            driver.read_display(channel)
            driver.set_front_output(channel, settings.FrontPanelOutputSource.COMPONENT)
            driver.get_front_output(channel)
        resource.write.assert_called_with(f"FPOP {int(channel)}, 1")
    for channel in settings.AuxiliaryChannel:
        for driver in (mock_instrument, virtual):
            driver.set_aux_out(channel, 0.5)
            driver.get_aux_out(channel)
            driver.get_aux_in(channel)
        resource.write.assert_called_with(f"AUXV {int(channel)}, 0.5")
    for driver in (mock_instrument, virtual):
        with pytest.raises(ValueError):
            driver.read_display(settings.AuxiliaryChannel.AUX1)


def test_register_names_positions_and_masks(mock_instrument, resource, virtual):
    for register, bits, flags, enable_command, status_query in REGISTER_TYPES:
        for bit in bits:
            mask = flags[bit.name]
            assert int(mask) == 1 << int(bit)
            for driver in (mock_instrument, virtual):
                driver.set_enable_register(register, mask)
                driver.set_enable_register(
                    register, settings.SwitchState.ON, decimal=False, bit=bit
                )
            resource.write.assert_called_with(f"{enable_command} {int(bit)},1")
            resource.query.return_value = "1"
            assert mock_instrument.get_enable_register(register, bit) == 1
            resource.query.assert_called_with(f"{enable_command}? {int(bit)}")
            assert mock_instrument.get_status_byte(register, bit) == 1
            resource.query.assert_called_with(f"{status_query} {int(bit)}")
            assert virtual.get_enable_register(register, bit) == 1
            assert virtual.get_status_byte(register, bit) in (0, 1)
        members = list(flags)
        combined = members[0] | members[-1]
        mock_instrument.set_enable_register(register, combined)
        resource.write.assert_called_with(f"{enable_command} {int(combined)}")
        resource.query.return_value = str(int(combined))
        assert flags(mock_instrument.get_status_byte(register)) == combined


def test_register_masks_positions_and_registers_cannot_be_mixed(
    mock_instrument, resource, virtual
):
    for driver in (mock_instrument, virtual):
        for operation in (
            lambda: driver.get_status_byte(
                settings.StatusRegister.ERROR, settings.SerialPollBit.ERROR
            ),
            lambda: driver.get_enable_register(
                settings.StatusRegister.ERROR, settings.ErrorFlag.RAM_ERROR
            ),
            lambda: driver.set_enable_register(
                settings.StatusRegister.ERROR, settings.ErrorBit.RAM_ERROR
            ),
            lambda: driver.set_enable_register(
                settings.StatusRegister.ERROR, settings.SerialPollFlag.ERROR
            ),
            lambda: driver.set_enable_register(
                settings.StatusRegister.ERROR,
                settings.ErrorFlag.RAM_ERROR,
                decimal=False,
                bit=settings.ErrorBit.RAM_ERROR,
            ),
        ):
            with pytest.raises(ValueError):
                operation()
    resource.write.assert_not_called()
    resource.query.assert_not_called()


def test_annotations_expose_enum_inputs_and_integer_getters():
    for cls in (sr830.SR830, virtual_sr830.VirtualSR830):
        for name, enum, command in NUMERIC_PROPERTIES:
            setter_hints = typing.get_type_hints(getattr(cls, name).fset)
            parameter = next(
                (value for key, value in setter_hints.items() if key != "return")
            )
            assert set(typing.get_args(parameter)) == {enum, int}
            assert typing.get_type_hints(getattr(cls, name).fget)["return"] is int
        assert inspect.signature(cls.connect) == inspect.signature(sr830.SR830.connect)
