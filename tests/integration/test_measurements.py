"""Basic instrument identity and finite measurements without a calibrated signal."""

import math
import pytest

from sr830 import AuxiliaryChannel, Channel, MeasurementParameter


def test_identification(instrument):
    fields = instrument.idn.split(",")
    assert len(fields) == 4
    assert fields[1].strip().upper() == "SR830"


@pytest.mark.parametrize("parameter", list(MeasurementParameter)[:4])
def test_measurement(instrument, parameter):
    assert math.isfinite(instrument.measure(parameter))


@pytest.mark.parametrize("channel", list(Channel))
def test_display_reading(instrument, channel):
    assert math.isfinite(instrument.read_display(channel))


@pytest.mark.parametrize("channel", list(AuxiliaryChannel))
def test_auxiliary_input(instrument, channel):
    assert math.isfinite(instrument.get_aux_in(channel))


def test_snapshot(instrument):
    parameters = [
        MeasurementParameter.X,
        MeasurementParameter.Y,
        MeasurementParameter.R,
    ]
    values = tuple(instrument.measure_multiple(parameters))
    assert len(values) == len(parameters)
    assert all(math.isfinite(value) for value in values)


def test_command_error_check(instrument):
    instrument.check_errors()
