"""Unit tests for sr830 library connected to an instrument."""
import argparse

import numpy as np
import pytest
import visa
import sr830

parser = argparse.ArgumentParser()
parser.add_argument(
    "-r", "--resource-name", help="VISA resource name",
)
parser.add_argument(
    "-o",
    "--output-interface",
    type=int,
    help="Output communication interface for reading instrument responses: 0 (RS232) or 1 (GPIB)",
)
args = parser.parse_args()

lia = sr830.sr830(resource_name=args.resource_name)


def test_connect():
    """Test for successful connection with minimal setup."""
    lia.connect(
        output_interface=args.output_interface, reset=False, local_lockout=False
    )
    assert lia.instr.session is not None


def test_reset():
    """Check reset command issued without errors."""
    lia.reset()


def test_get_enable_register():
    """Test query of all status register enables.
    
    All should be disabled after a reset.
    """
    assert lia.get_enable_register("standard_event") == 0
    assert lia.get_enable_register("serial_poll") == 0
    assert lia.get_enable_register("error") == 0
    assert lia.get_enable_register("lia_status") == 0


def test_enable_all_status_bytes():
    """Check command can be issued without errors."""
    lia.enable_all_status_bytes()

    # check all are enabled
    assert lia.get_enable_register("standard_event") == 255
    assert lia.get_enable_register("serial_poll") == 255
    assert lia.get_enable_register("error") == 255
    assert lia.get_enable_register("lia_status") == 255


def test_error_check():
    """Check command can be issued without errors."""
    lia.error_check()


def test_reference_phase_shift():
    """Test read/write of reference phase shift."""
    # read the ref phase shift
    old_phase_shift = lia.reference_phase_shift
    assert (old_phase_shift >= -360) and (old_phase_shift <= 720)

    # try a new valid phase shift
    while True:
        new_phase_shift = np.random.uniform(-360, 720, 1)
        if new_phase_shift != old_phase_shift:
            break
    lia.reference_phase_shift = new_phase_shift
    assert lia.reference_phase_shift == new_phase_shift

    # try an invalid phase shift
    with pytest.raises(ValueError):
        new_phase_shift = 10000
        lia.reference_phase_shift = new_phase_shift


def test_reference_source():
    """Test read/write of reference source."""
    # read old ref source
    old_source = lia.reference_source
    assert old_source in [0, 1]

    # change to the opposite source
    if old_source == 0:
        new_source = 1
    else:
        new_source = 0
    lia.reference_source = new_source
    assert lia.reference_source == new_source

    # change back
    lia.reference_source = old_source

    # try an invalid source
    with pytest.raises(ValueError):
        new_source = 2
        lia.reference_source = new_source


def test_reference_frequency():
    """Test read/write of reference frequency."""
    # read current ref frequency
    old_freq = lia.reference_frequency
    assert (old_freq >= 0.001) and (old_freq <= 102000)

    # try a new valid frequency
    while True:
        new_freq = np.random.uniform(0.001, 102000, 1)
        if new_freq != old_freq:
            break
    lia.reference_frequency = new_freq
    assert lia.reference_frequency == new_freq

    # change back
    lia.reference_frequency = old_freq

    # try an invalid source
    with pytest.raises(ValueError):
        new_freq = 0
        lia.reference_frequency = new_freq


def test_reference_trigger():
    """Test read/write of reference trigger."""
    # read old ref trigger
    old_trigger = lia.reference_trigger
    assert old_trigger in range(3)

    # change to another trigger
    if old_trigger in [0, 2]:
        new_trigger = 1
    else:
        new_trigger = 0
    lia.reference_trigger = new_trigger
    assert lia.reference_trigger == new_trigger

    # change back
    lia.reference_trigger = old_trigger

    # try an invalid trigger
    with pytest.raises(ValueError):
        new_trigger = 3
        lia.reference_trigger = new_trigger


def test_harmonic():
    """Test read/write of harmonic."""
    # read current harmonic
    old_harmonic = lia.harmonic
    assert (old_harmonic >= 1) and (old_harmonic <= 19999)

    # try a new valid harmonic
    while True:
        new_harmonic = int(np.random.uniform(1, 19999, 1))
        if new_harmonic != old_harmonic:
            break
    lia.harmonic = new_harmonic
    assert lia.harmonic == new_harmonic

    # change back
    lia.harmonic = old_harmonic

    # try an invalid harmonic
    with pytest.raises(ValueError):
        new_harmonic = 0
        lia.harmonic = new_harmonic


def test_sine_amplitude():
    """Test read/write of sine_amplitude."""
    # read current sine amp
    old_amp = lia.sine_amplitude
    assert (old_amp >= 0.004) and (old_amp <= 5.000)

    # try a new valid amp
    while True:
        new_amp = np.random.uniform(0.004, 5.000, 1)
        if new_amp != old_amp:
            break
    lia.sine_amplitude = new_amp
    assert lia.sine_amplitude == new_amp

    # change back
    lia.sine_amplitude = old_amp

    # try an invalid amp
    with pytest.raises(ValueError):
        new_amp = 0
        lia.sine_amplitude = new_amp


def test_input_configuration():
    """Test read/write of input configuration."""
    # read old config
    old_config = lia.input_configuration
    assert old_config in range(4)

    # change to another config
    if old_config in [0, 2, 3]:
        new_config = 1
    else:
        new_config = 0
    lia.input_configuration = new_config
    assert lia.input_configuration == new_config

    # change back
    lia.input_configuration = old_config

    # try an invalid config
    with pytest.raises(ValueError):
        new_config = 4
        lia.input_configuration = new_config


def test_input_shield_grounding():
    """Test read/write of input shield grounding."""
    # read old grounding
    old_ground = lia.input_shield_grounding
    assert old_ground in [0, 1]

    # change to another grounding
    if old_ground == 0:
        new_ground = 1
    else:
        new_ground = 0
    lia.input_shield_grounding = new_ground
    assert lia.input_shield_grounding == new_ground

    # change back
    lia.input_shield_grounding = old_ground

    # try an invalid grounding
    with pytest.raises(ValueError):
        new_ground = 2
        lia.input_shield_grounding = new_ground


def test_input_coupling():
    """Test read/write of input coupling."""
    # read old coupling
    old_coupling = lia.input_coupling
    assert old_coupling in [0, 1]

    # change to another coupling
    if old_coupling == 0:
        new_coupling = 1
    else:
        new_coupling = 0
    lia.input_coupling = new_coupling
    assert lia.input_coupling == new_coupling

    # change back
    lia.input_coupling = old_coupling

    # try an invalid coupling
    with pytest.raises(ValueError):
        new_coupling = 2
        lia.input_coupling = new_coupling


def test_disconnect():
    """Test for successful disconnection."""
    lia.disconnect()
    with pytest.raises(visa.InvalidSession):
        lia.instr.session
