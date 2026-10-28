"""Verify backend selection and fixture cleanup using fake VISA, never hardware."""

import argparse
from unittest.mock import patch

import pytest
from pyvisa.constants import Parity, StopBits

from sr830 import SR830
from tests.support import (
    InstrumentOptions,
    open_instrument,
    positive_float,
    positive_int,
    preserve_settings,
)
from virtual_sr830 import VirtualSR830


def test_default_backend_never_constructs_a_visa_manager():
    with patch("tests.support.pyvisa.ResourceManager") as factory:
        with open_instrument(InstrumentOptions()) as instrument:
            assert isinstance(instrument, VirtualSR830)
            assert instrument._connected
        assert not instrument._connected
        factory.assert_not_called()


def test_explicit_hardware_backend_and_serial_options(manager, resource, query_replies):
    query_replies["*IDN?"] = "Stanford_Research_Systems,SR830,1234,1.07"
    options = InstrumentOptions(
        resource_name="serial-alias",
        visa_backend="@py",
        output_interface=0,
        visa_timeout=2500,
        baud_rate=19200,
        data_bits=8,
        parity="even",
        stop_bits=1.5,
        write_termination="CR",
    )
    with patch("tests.support.pyvisa.ResourceManager", return_value=manager) as factory:
        with open_instrument(options) as instrument:
            assert isinstance(instrument, SR830)
            assert instrument._instr is resource
            assert resource.timeout == 2500
            assert resource.baud_rate == 19200
            assert resource.data_bits == 8
            assert resource.parity is Parity.even
            assert resource.stop_bits is StopBits.one_and_a_half
            assert resource.write_termination == "\r"
        factory.assert_called_once_with("@py")
    manager.open_resource.assert_called_once_with("serial-alias")
    resource.close.assert_called_once()
    manager.close.assert_called_once()


@pytest.mark.parametrize("failure_stage", ["open", "identity", "test"])
def test_hardware_failure_closes_owned_connections_and_never_falls_back(
    manager, resource, query_replies, failure_stage
):
    query_replies["*IDN?"] = "SRS,SR830,1234,1.07"
    if failure_stage == "open":
        manager.open_resource.side_effect = OSError("open failed")
    elif failure_stage == "identity":
        resource.query.side_effect = OSError("identity failed")
    with patch("tests.support.pyvisa.ResourceManager", return_value=manager):
        with pytest.raises(OSError):
            with open_instrument(InstrumentOptions(resource_name="explicit-resource")):
                raise OSError("test failed")
    manager.close.assert_called_once()
    if failure_stage != "open":
        resource.close.assert_called_once()


@pytest.mark.parametrize("identity", ["other-device", "Vendor,OTHER_MODEL,1234,1.0"])
def test_wrong_device_is_closed_before_tests_can_change_settings(
    manager, resource, query_replies, identity
):
    query_replies["*IDN?"] = identity
    with patch("tests.support.pyvisa.ResourceManager", return_value=manager):
        with pytest.raises(AssertionError, match="Expected an SR830"):
            with open_instrument(InstrumentOptions(resource_name="wrong-model")):
                pytest.fail("The fixture must not yield an unrelated device.")
    resource.close.assert_called_once()
    manager.close.assert_called_once()


def test_settings_are_restored_after_an_assertion():
    instrument = VirtualSR830()
    instrument.connect("ASRL1::INSTR")
    original = instrument.reference_frequency
    with pytest.raises(AssertionError):
        with preserve_settings(instrument, "reference_frequency"):
            instrument.reference_frequency = 1234.0
            raise AssertionError("test failure")
    assert instrument.reference_frequency == original


def test_cleanup_attempts_remaining_settings_if_one_restore_fails():
    class FailingRestore:
        first = 1

        @property
        def second(self):
            return 2

        @second.setter
        def second(self, value):
            raise OSError("restore failed")

    instrument = FailingRestore()
    with pytest.raises(OSError, match="restore failed"):
        with preserve_settings(instrument, "first", "second"):
            instrument.first = 42
    assert instrument.first == 1


@pytest.mark.parametrize(
    "parser,value",
    [
        (positive_int, "0"),
        (positive_int, "-1"),
        (positive_float, "0"),
        (positive_float, "-1"),
        (positive_float, "nan"),
        (positive_float, "inf"),
    ],
)
def test_invalid_timeout_values(parser, value):
    with pytest.raises(argparse.ArgumentTypeError):
        parser(value)
