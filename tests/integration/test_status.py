"""Register read/write checks shared by hardware and simulation."""

import pytest

from sr830 import StatusRegister


@pytest.mark.parametrize("register", list(StatusRegister))
def test_enable_register_round_trip(instrument, register):
    previous = instrument.get_enable_register(register)
    try:
        instrument.set_enable_register(register, 0)
        assert instrument.get_enable_register(register) == 0
    finally:
        instrument.set_enable_register(register, previous)


@pytest.mark.parametrize("register", list(StatusRegister))
def test_status_register_read(instrument, register):
    value = instrument.get_status_byte(register)
    assert type(value) is int
    assert 0 <= value <= 255
