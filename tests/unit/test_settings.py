"""Representative command routing and response parsing against literal wire codes."""

import pytest

from sr830 import settings
from tests.cases import SETTING_CASES


@pytest.mark.parametrize(
    "name,value,expected_command",
    SETTING_CASES,
    ids=[name for name, _, _ in SETTING_CASES],
)
def test_setting_wire_contract(
    mock_instrument, resource, query_replies, name, value, expected_command
):
    command, code = expected_command.split()
    query_replies.update({"OUTX?": "1", f"{command}?": code})
    setattr(mock_instrument, name, value)
    resource.write.assert_called_once_with(expected_command)
    assert getattr(mock_instrument, name) == int(code)
    resource.query.assert_called_with(f"{command}?")


def test_plain_integer_codes_remain_supported(mock_instrument, resource):
    mock_instrument.sensitivity = 8
    resource.write.assert_called_once_with("SENS 8")
    resource.query.return_value = "8"
    result = mock_instrument.sensitivity
    assert result == 8
    assert type(result) is int


@pytest.mark.parametrize(
    "channel,display,ratio,expected_command,reply",
    [
        (
            1,
            settings.Channel1Display.AUX_IN_2,
            settings.Channel1Ratio.AUX_IN_1,
            "DDEF 1, 4, 1",
            "4,1",
        ),
        (
            2,
            settings.Channel2Display.PHASE,
            settings.Channel2Ratio.AUX_IN_4,
            "DDEF 2, 1, 2",
            "1,2",
        ),
    ],
    ids=["ch1-aux", "ch2-phase"],
)
def test_display_wire_contract(
    mock_instrument, resource, channel, display, ratio, expected_command, reply
):
    mock_instrument.set_display(channel, display, ratio)
    resource.write.assert_called_once_with(expected_command)
    resource.query.return_value = reply
    assert mock_instrument.get_display(channel) == tuple(map(int, reply.split(",")))
    resource.query.assert_called_once_with(f"DDEF? {channel}")


def test_front_output_wire_contract(mock_instrument, resource):
    mock_instrument.set_front_output(
        settings.Channel.CH2, settings.FrontPanelOutputSource.DISPLAY
    )
    resource.write.assert_called_once_with("FPOP 2, 0")
    resource.query.return_value = "0"
    assert mock_instrument.get_front_output(settings.Channel.CH2) == 0
    resource.query.assert_called_once_with("FPOP? 2")


def test_offset_and_expansion_wire_contract(mock_instrument, resource):
    mock_instrument.set_output_offset_expand(
        settings.OutputParameter.R, 12.5, settings.OutputExpansion.x100
    )
    resource.write.assert_called_with("OEXP 3, 12.5, 2")
    resource.query.return_value = "12.5,2"
    assert mock_instrument.get_output_offset_expand(settings.OutputParameter.R) == (
        12.5,
        2,
    )
    resource.query.assert_called_once_with("OEXP? 3")
    mock_instrument.auto_offset(settings.OutputParameter.R)
    resource.write.assert_called_with("AOFF 3")


def test_auxiliary_wire_contract(mock_instrument, resource, query_replies):
    mock_instrument.set_aux_out(settings.AuxiliaryChannel.AUX3, 0.5)
    resource.write.assert_called_once_with("AUXV 3, 0.5")
    query_replies.update({"AUXV? 3": "0.5", "OAUX? 3": "-1.25"})
    assert mock_instrument.get_aux_out(settings.AuxiliaryChannel.AUX3) == 0.5
    assert mock_instrument.get_aux_in(settings.AuxiliaryChannel.AUX3) == -1.25


def test_harmonic_read_and_write(mock_instrument, resource):
    mock_instrument.harmonic = 2
    resource.write.assert_called_once_with("HARM 2")
    resource.query.return_value = "2"
    assert mock_instrument.harmonic == 2
    resource.query.assert_called_once_with("HARM?")
