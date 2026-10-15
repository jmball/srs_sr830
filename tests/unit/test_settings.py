"""Each setting code has identical integer/enum behavior in both drivers."""

from enum import IntEnum

import pytest
import sr830
import sr830.settings as settings
import virtual_sr830

from tests.cases import SETTING_COMMANDS


@pytest.mark.parametrize(
    "enum",
    sorted({enum for _, enum, _ in SETTING_COMMANDS}, key=lambda enum: enum.__name__),
)
def test_categorical_enums_are_shared_and_use_command_codes(enum):
    assert issubclass(enum, IntEnum)
    assert getattr(sr830, enum.__name__) is enum
    assert getattr(virtual_sr830, enum.__name__) is enum
    assert [int(member) for member in enum] == list(range(len(enum)))


@pytest.mark.parametrize(
    "name,member,command",
    [
        pytest.param(name, member, command, id=f"{name}-{member.name}")
        for name, enum, command in SETTING_COMMANDS
        for member in enum
    ],
)
@pytest.mark.parametrize("as_integer", [False, True], ids=["enum", "integer"])
def test_setting_codes_emit_commands_and_return_integers(
    mock_instrument, resource, virtual, name, member, command, as_integer
):
    value = int(member) if as_integer else member
    setattr(mock_instrument, name, value)
    resource.write.assert_called_with(f"{command} {int(member)}")
    resource.query.return_value = str(int(member))
    result = getattr(mock_instrument, name)
    assert type(result) is int
    assert result == int(member)
    setattr(virtual, name, value)
    result = getattr(virtual, name)
    assert type(result) is int
    assert result == int(member)


@pytest.mark.parametrize("name,enum,command", SETTING_COMMANDS)
@pytest.mark.parametrize("driver_class", [sr830.SR830, virtual_sr830.VirtualSR830])
def test_invalid_integer_codes_still_raise(driver_class, name, enum, command):
    with pytest.raises(ValueError):
        setattr(driver_class(), name, len(enum))


@pytest.mark.parametrize(
    "channel,display,ratio",
    [
        (1, settings.Channel1Display.AUX_IN_2, settings.Channel1Ratio.AUX_IN_1),
        (2, settings.Channel2Display.PHASE, settings.Channel2Ratio.AUX_IN_4),
    ],
)
def test_display_enums_preserve_integer_tuple_returns(
    mock_instrument, resource, virtual, channel, display, ratio
):
    mock_instrument.set_display(channel, display, ratio)
    resource.write.assert_called_with(f"DDEF {channel}, {int(display)}, {int(ratio)}")
    virtual.set_display(channel, display, ratio)
    result = virtual.get_display(channel)
    assert result == (int(display), int(ratio))
    assert all(type(value) is int for value in result)
    mock_instrument.set_front_output(channel, settings.FrontPanelOutputSource.COMPONENT)
    resource.write.assert_called_with(f"FPOP {channel}, 1")
    virtual.set_front_output(channel, settings.FrontPanelOutputSource.COMPONENT)
    assert type(virtual.get_front_output(channel)) is int
    assert virtual.get_front_output(channel) == 1


def test_connect_accepts_named_output_interface(virtual):
    virtual.connect(
        "TCPIP0::example.invalid::1234::SOCKET",
        output_interface=settings.OutputInterface.GPIB,
    )
    assert type(virtual.output_interface) is int
    assert virtual.output_interface == 1
    virtual.disconnect()
