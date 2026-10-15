"""Real register read/write checks; virtual registers are not implemented."""

import pytest
from sr830 import StatusRegister

pytestmark = pytest.mark.hardware


@pytest.mark.parametrize("register", list(StatusRegister))
def test_enable_register_round_trip(hardware_instrument, register):
    previous = hardware_instrument.get_enable_register(register)
    try:
        hardware_instrument.set_enable_register(register, 0)
        assert hardware_instrument.get_enable_register(register) == 0
    finally:
        hardware_instrument.set_enable_register(register, previous)


@pytest.mark.parametrize("register", list(StatusRegister))
def test_status_register_read(hardware_instrument, register):
    value = hardware_instrument.get_status_byte(register)
    assert type(value) is int
    assert 0 <= value <= 255
