"""Public setting round trips on VirtualSR830 or the CLI-selected instrument."""

import pytest

from sr830 import (
    AuxiliaryChannel,
    Channel,
    Channel1Display,
    Channel1Ratio,
    Channel2Display,
    Channel2Ratio,
    EndOfBufferMode,
    FrontPanelOutputSource,
    InputConfiguration,
    InputCoupling,
    InputShieldGrounding,
    LineNotchFilter,
    LocalMode,
    LowPassFilterSlope,
    OutputExpansion,
    OutputParameter,
    ReserveMode,
    SampleRate,
    Sensitivity,
    SwitchState,
    SynchronousFilter,
    TimeConstant,
    TriggerStartMode,
)
from tests.support import preserve_settings


@pytest.mark.parametrize(
    "name,value",
    [
        ("reference_phase_shift", 30.25),
        ("sine_amplitude", 0.02),
        ("input_shield_grounding", InputShieldGrounding.FLOAT),
        ("input_coupling", InputCoupling.AC),
        ("line_notch_filter_status", LineNotchFilter.OFF),
        ("sensitivity", Sensitivity.x1m),
        ("reserve_mode", ReserveMode.NORMAL),
        ("time_constant", TimeConstant.ms_100),
        ("lowpass_filter_slope", LowPassFilterSlope.dB_12),
        ("sync_filter_status", SynchronousFilter.OFF),
        ("key_click_state", SwitchState.OFF),
        ("alarm_status", SwitchState.OFF),
        ("sample_rate", SampleRate.Hz_16),
        ("end_of_buffer_mode", EndOfBufferMode.ONE_SHOT),
        ("trigger_start_mode", TriggerStartMode.OFF),
        ("local_mode", LocalMode.REMOTE),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_setting_round_trip(instrument, name, value):
    # These can change each other indirectly, so preserve them together.
    # Cleanup restores input/gain/reserve before filter/time constant, which
    # avoids clamping a short time constant against a temporary gain setting.
    related = (
        "time_constant",
        "lowpass_filter_slope",
        "reserve_mode",
        "sensitivity",
        "input_configuration",
    )
    names = tuple(dict.fromkeys((*related, name)))
    with preserve_settings(instrument, *names):
        instrument.input_configuration = InputConfiguration.A
        instrument.sensitivity = Sensitivity.x1
        instrument.reserve_mode = ReserveMode.NORMAL
        instrument.lowpass_filter_slope = LowPassFilterSlope.dB_6
        instrument.time_constant = TimeConstant.ms_300
        setattr(instrument, name, value)
        assert getattr(instrument, name) == pytest.approx(value, abs=0.001)


def test_internal_reference_frequency(internal_reference):
    internal_reference.reference_frequency = 1234.0
    assert internal_reference.reference_frequency == pytest.approx(1234.0, rel=1e-4)


@pytest.mark.parametrize(
    "channel,display,ratio",
    [
        (Channel.CH1, Channel1Display.R, Channel1Ratio.NONE),
        (Channel.CH2, Channel2Display.PHASE, Channel2Ratio.NONE),
    ],
)
def test_display_round_trip(instrument, channel, display, ratio):
    previous = instrument.get_display(channel)
    try:
        instrument.set_display(channel, display, ratio)
        assert instrument.get_display(channel) == (int(display), int(ratio))
    finally:
        instrument.set_display(channel, *previous)


@pytest.mark.parametrize("parameter", list(OutputParameter))
def test_output_offset_and_expansion(instrument, parameter):
    previous = instrument.get_output_offset_expand(parameter)
    try:
        instrument.set_output_offset_expand(parameter, 0.0, OutputExpansion.x1)
        offset, expansion = instrument.get_output_offset_expand(parameter)
        assert offset == pytest.approx(0.0, abs=0.01)
        assert expansion == int(OutputExpansion.x1)
    finally:
        instrument.set_output_offset_expand(parameter, *previous)


@pytest.mark.parametrize(
    "name,value",
    [
        ("reference_phase_shift", 721),
        ("reference_frequency", 102001),
        ("harmonic", 0),
        ("sine_amplitude", 0),
        ("sensitivity", 27),
        ("time_constant", 20),
        ("sample_rate", 15),
    ],
)
def test_invalid_settings(instrument, name, value):
    with pytest.raises(ValueError):
        setattr(instrument, name, value)


@pytest.mark.parametrize("channel", list(Channel))
def test_front_output_round_trip(instrument, channel):
    previous = instrument.get_front_output(channel)
    try:
        instrument.set_front_output(channel, FrontPanelOutputSource.DISPLAY)
        assert instrument.get_front_output(channel) == int(
            FrontPanelOutputSource.DISPLAY
        )
    finally:
        instrument.set_front_output(channel, previous)


@pytest.mark.parametrize("channel", list(AuxiliaryChannel))
def test_auxiliary_output_round_trip(instrument, channel):
    previous = instrument.get_aux_out(channel)
    try:
        instrument.set_aux_out(channel, 0.125)
        assert instrument.get_aux_out(channel) == pytest.approx(0.125, abs=0.001)
    finally:
        instrument.set_aux_out(channel, previous)
