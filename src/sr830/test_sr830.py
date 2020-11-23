"""Unit tests for sr830 library connected to an instrument."""
import argparse
import math
import random
import time

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
    help=(
        "Output communication interface for reading instrument responses: 0 (RS232) "
        + "or 1 (GPIB)"
    ),
)
args = parser.parse_args()

lia = sr830.sr830()


def _int_property_test(settings, lia_property):
    """Test read/write of a property that has integer settings."""
    # check read of current setting
    old_setting = lia_property
    assert old_setting in settings

    # check write/read of all valid settings
    for new_setting in settings:
        lia_property = new_setting
        assert lia_property == new_setting

    # change back to old setting
    lia_property = old_setting

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_setting = max(settings) + 1
        lia_property = new_setting


def _float_property_test(min_value, max_value, lia_property):
    """Test read/write of a float property."""
    # read current value
    old_value = lia_property
    assert (old_value >= min_value) and (old_value <= max_value)

    # try a new valid amp
    while True:
        new_value = np.random.uniform(min_value, max_value, 1)
        if new_value != old_value:
            break
    lia_property = new_value
    assert lia_property == new_value

    # change back
    lia_property = old_value

    # try an invalid amp
    with pytest.raises(ValueError):
        new_value = max_value + 1
        lia_property = new_value


def test_connect():
    """Test for successful connection with minimal setup."""
    lia.connect(
        args.resource_name,
        output_interface=args.output_interface,
        reset=False,
        local_lockout=False,
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


def test_set_enable_register():
    """Test set enable register function."""
    registers = list(lia._enable_register_cmd_dict.keys())
    dec_value = range(256)

    for reg in registers:
        old_val = lia.get_enable_register(reg)

        new_val = random.choice(dec_value)
        lia.set_enable_register(reg, new_val)
        new_val_set = lia.get_enable_register(reg)
        assert new_val_set == new_val

        lia.set_enable_register(reg, old_val)

    with pytest.raises(ValueError):
        new_val = max(dec_value) + 1
        reg = random.choice(registers)
        lia.set_enable_register(reg, new_val)

    with pytest.raises(ValueError):
        new_val = random.choice(dec_value)
        reg = "hello"
        lia.set_enable_register(reg, new_val)


def test_enable_all_status_bytes():
    """Check command can be issued without errors."""
    lia.enable_all_status_bytes()

    # check all are enabled
    assert lia.get_enable_register("standard_event") == 255
    assert lia.get_enable_register("serial_poll") == 255
    assert lia.get_enable_register("error") == 255
    assert lia.get_enable_register("lia_status") == 255


def test_get_status_byte():
    """Test get status byte function."""
    assert type(lia.get_status_byte("standard_event")) is int
    assert type(lia.get_status_byte("serial_poll")) is int
    assert type(lia.get_status_byte("error")) is int
    assert type(lia.get_status_byte("lia_status")) is int


def test_errors():
    """Check errors property."""
    lia.errors


def test_reference_phase_shift():
    """Test read/write of reference phase shift."""
    _float_property_test(-360, 720, lia.reference_phase_shift)


def test_reference_source():
    """Test read/write of reference source."""
    settings = range(2)
    _int_property_test(settings, lia.reference_source)


def test_reference_frequency():
    """Test read/write of reference frequency."""
    _float_property_test(0.001, 102000, lia.reference_frequency)


def test_reference_trigger():
    """Test read/write of reference trigger."""
    settings = range(3)
    _int_property_test(settings, lia.reference_trigger)


def test_harmonic():
    """Test read/write of harmonic."""
    settings = range(1, 20000)
    _int_property_test(settings, lia.harmonic)


def test_sine_amplitude():
    """Test read/write of sine_amplitude."""
    _float_property_test(0.004, 5.000, lia.sine_amplitude)


def test_input_configuration():
    """Test read/write of input configuration."""
    settings = range(4)
    _int_property_test(settings, lia.input_configuration)


def test_input_shield_grounding():
    """Test read/write of input shield grounding."""
    settings = range(2)
    _int_property_test(settings, lia.input_shield_grounding)


def test_input_coupling():
    """Test read/write of input coupling."""
    settings = range(2)
    _int_property_test(settings, lia.input_coupling)


def test_line_notch_filter_status():
    """Test read/write of line notch filter status."""
    settings = range(4)
    _int_property_test(settings, lia.line_notch_filter_status)


def test_sensitivity():
    """Test read/write of sensitivity."""
    settings = range(27)
    _int_property_test(settings, lia.sensitivity)


def test_reserve_mode():
    """Test read/write of reserve mode."""
    settings = range(3)
    _int_property_test(settings, lia.reserve_mode)


def test_time_constant():
    """Test read/write of time constant."""
    settings = range(20)
    _int_property_test(settings, lia.time_constant)


def test_lowpass_filter_slope():
    """Test read/write of low pass filter slope."""
    settings = range(4)
    _int_property_test(settings, lia.lowpass_filter_slope)


def test_sync_filter_status():
    """Test read/write of synchronous filter status."""
    settings = range(2)
    _int_property_test(settings, lia.sync_filter_status)


def test_output_interface():
    """Test read/write of output interface."""
    settings = range(2)
    _int_property_test(settings, lia.output_interface)


def test_get_display():
    """Test reading both displays."""
    channel_settings = range(1, 3)
    display_settings = range(5)
    ratio_settings = range(3)

    # check all valid settings
    for channel in channel_settings:
        old_display, old_ratio = lia.get_display(channel)
        assert old_display in display_settings
        assert old_ratio in ratio_settings

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_channel = max(channel_settings) + 1
        lia.get_display(new_channel)


def test_set_display():
    """Test setting display settings."""
    channel_settings = range(1, 3)
    display_settings = range(5)
    ratio_settings = range(3)

    for channel in channel_settings:
        old_display, old_ratio = lia.get_display(channel)

        # check write/read of all valid settings
        for new_display in display_settings:
            for new_ratio in ratio_settings:
                lia.set_display(channel, new_display, new_ratio)
                new_display_set, new_ratio_set = lia.get_display(channel)
                assert new_display == new_display_set
                assert new_ratio == new_ratio_set

        # change back to old setting
        lia.set_display(channel, old_display, old_ratio)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_channel = max(channel_settings) + 1
        new_display = max(display_settings) + 1
        new_ratio = max(display_settings) + 1
        lia.set_display(new_channel, new_display, new_ratio)


def test_get_front_output():
    """Test reading front ouptut."""
    channel_settings = range(1, 3)
    output_settings = range(2)

    # check all valid settings
    for channel in channel_settings:
        old_output = lia.get_front_output(channel)
        assert old_output in output_settings

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_channel = max(channel_settings) + 1
        lia.get_front_output(new_channel)


def test_set_front_output():
    """Test setting front output."""
    channel_settings = range(1, 3)
    output_settings = range(2)

    for channel in channel_settings:
        old_output = lia.get_front_output(channel)

        # check write/read of all valid settings
        for new_output in output_settings:
            lia.set_front_output(channel, new_output)
            new_output_set = lia.get_front_output(channel)
            assert new_output == new_output_set

        # change back to old setting
        lia.set_front_output(channel, old_output)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_channel = max(channel_settings) + 1
        new_output = max(output_settings) + 1
        lia.set_front_output(new_channel, new_output)


def test_get_output_offset_expand():
    """Test reading front ouptut."""
    parameter_settings = range(1, 4)
    min_offset = -105.00
    max_offset = 105.00
    expand_settings = range(3)

    # check all valid settings
    for parameter in parameter_settings:
        old_offset, old_expand = lia.get_output_offset_expand(parameter)
        assert (old_offset >= min_offset) and (old_offset <= max_offset)
        assert old_expand in expand_settings

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_parameter = max(parameter_settings) + 1
        lia.get_output_offset_expand(new_parameter)


def test_set_output_offset_expand():
    """Test setting front output."""
    parameter_settings = range(1, 4)
    min_offset = -105.00
    max_offset = 105.00
    expand_settings = range(3)

    for parameter in parameter_settings:
        old_offset, old_expand = lia.get_output_offset_expand(parameter)

        # check write/read of all valid settings
        for new_expand in expand_settings:
            while True:
                new_offset = np.random.uniform(min_offset, max_offset, 1)
                if new_offset != old_offset:
                    break
            lia.set_output_offset_expand(parameter, new_offset, new_expand)
            new_offset_set, new_expand_set = lia.get_output_offset_expand(parameter)
            assert new_offset == new_offset_set
            assert new_expand == new_expand_set

        # change back to old setting
        lia.set_output_offset_expand(parameter, old_offset, old_expand)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_parameter = max(parameter_settings) + 1
        new_offset = max_offset + 1
        new_expand = max(expand_settings) + 1
        lia.set_output_offset_expand(new_parameter, new_offset, new_expand)


def test_auto_offset():
    """Test auto offset function."""
    parameter_settings = range(1, 4)

    # check command issed without error
    for parameter in parameter_settings:
        lia.auto_offset(parameter)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_parameter = max(parameter_settings) + 1
        lia.auto_offset(new_parameter)


def test_get_aux_in():
    """Test reading aux input function."""
    aux_in_settings = range(1, 5)
    min_voltage = -10.0
    max_voltage = 10.0

    # check command issed without error
    for aux_in in aux_in_settings:
        voltage = lia.get_aux_in(aux_in)
        assert (voltage >= min_voltage) and (voltage <= max_voltage)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_aux_in = max(aux_in_settings) + 1
        lia.get_aux_in(new_aux_in)


def test_get_aux_out():
    """Test reading aux output function."""
    aux_out_settings = range(1, 5)
    min_voltage = -10.0
    max_voltage = 10.0

    # check command issed without error
    for aux_out in aux_out_settings:
        voltage = lia.get_aux_out(aux_out)
        assert (voltage >= min_voltage) and (voltage <= max_voltage)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_aux_out = max(aux_out_settings) + 1
        lia.get_aux_out(new_aux_out)


def test_set_aux_out():
    """Test reading aux output function."""
    aux_out_settings = range(1, 5)
    min_voltage = -10.0
    max_voltage = 10.0

    for aux_out in aux_out_settings:
        old_voltage = lia.get_aux_out(aux_out)

        while True:
            new_voltage = np.random.uniform(min_voltage, max_voltage, 1)
            if new_voltage != old_voltage:
                break
        lia.set_aux_out(aux_out, new_voltage)
        new_voltage_set = lia.get_aux_out(aux_out)
        assert math.isclose(new_voltage, new_voltage_set, rel_tol=0.05)

        # set back to old value
        lia.set_aux_out(aux_out, old_voltage)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_aux_out = max(aux_out_settings) + 1
        new_voltage = max_voltage + 1
        lia.set_aux_out(new_aux_out, new_voltage)


def test_key_click_state():
    """Test read/write key click state property."""
    settings = range(2)
    _int_property_test(settings, lia.key_click_state)


def test_alarm_state():
    """Test read/write alarm property."""
    settings = range(2)
    _int_property_test(settings, lia.alarm_status)


def test_recall_setup():
    """Test recall setup function."""
    settings = range(1, 10)

    # check command processed without errors
    for setting in settings:
        lia.recall_setup(setting)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_setting = max(settings) + 1
        lia.recall_setup(new_setting)


def test_save_setup():
    """Test save setup function."""
    settings = range(1, 10)

    # check commands processed without errors
    for setting in settings:
        # overwrite save setting with existing setting to avoid loss
        lia.recall_setup(setting)
        lia.save_setup(setting)

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_setting = max(settings) + 1
        lia.save_setup(new_setting)


def test_auto_gain():
    """Test auto gain function."""
    lia.auto_gain()


def test_auto_reserve():
    """Test auto reserve function."""
    lia.auto_reserve()


def test_auto_phase():
    """Test auto reserve function."""
    lia.auto_phase()


def test_sample_rate():
    """Test read/write sample rate property."""
    settings = range(15)
    _int_property_test(settings, lia.sample_rate)


def test_end_of_buffer_mode():
    """Test read/write end of buffer mode property."""
    settings = range(2)
    _int_property_test(settings, lia.end_of_buffer_mode)


def test_trigger():
    """Test software trigger."""
    lia.trigger()


def test_trigger_start_mode():
    """Test read/write trigger start mode property."""
    settings = range(2)
    _int_property_test(settings, lia.trigger_start_mode)


def test_data_transfer_mode():
    """Test data transfer mode property."""
    settings = range(3)
    _int_property_test(settings, lia.data_transfer_mode)


def test_reset_data_buffers():
    """Test reset data buffers function."""
    lia.reset_data_buffers()


def test_start_pause_reset_cycle():
    """Test start, pause, reset cycle."""
    old_mode = lia.data_transfer_mode

    # cycle with fast transfer mode off
    lia.data_transfer_mode = 0
    lia.start()
    lia.pause()
    lia.reset_data_buffers()

    # TODO: complete test for fast data transfer
    # cycle with fast data transfer on if available
    # if args.resource_name.startswith("GPIB"):
    #     lia.data_transfer_mode = 0
    #     lia.start()
    #     lia.pause()
    #     lia.reset_data_buffers()


def test_measure():
    """Test single measurement function."""
    parameters = range(1, 5)

    for parameter in parameters:
        value = lia.measure(parameter)
        assert type(value) == float

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_setting = max(parameters) + 1
        lia.measure(new_setting)


def test_read_display():
    """Test read display function."""
    channels = range(1, 3)

    for channel in channels:
        value = lia.read_display(channel)
        assert type(value) == float

    # make sure invalid setting raises an error
    with pytest.raises(ValueError):
        new_setting = max(channels) + 1
        lia.read_display(new_setting)


def test_measure_multiple():
    """Test multiple measurement function."""
    parameters = range(1, 12)

    for i in range(2, 7):
        # take a random sample of parameters of length i to measure
        test_parameters = random.sample(parameters, i)
        values = lia.measure_multiple(test_parameters)
        assert len(values) == len(test_parameters)
        for value in values:
            assert type(value) == float

    # make sure invalid setting in list raises an error
    with pytest.raises(ValueError):
        new_setting = [max(parameters) + 1, 1, 2]
        lia.measure_multiple(new_setting)

    # make sure invalid list lengths raise errors
    with pytest.raises(ValueError):
        new_setting = range(2, 8)
        lia.measure_multiple(new_setting)
    with pytest.raises(ValueError):
        new_setting = [1]
        lia.measure_multiple(new_setting)


def test_buffer_size():
    """Test buffer size property."""
    buffer_sizes = range(16384)

    # add some data to the buffer
    lia.trigger_start_mode = 0
    lia.end_of_buffer_mode = 0
    lia.sample_rate = 13
    lia.data_transfer_mode = 0
    lia.reset_data_buffers()
    lia.start()
    time.sleep(0.5)
    lia.pause()

    size = lia.buffer_size
    assert (size >= min(buffer_sizes)) and (size <= max(buffer_sizes))
    assert type(size) is int

    lia.reset_data_buffers()


def _get_buffer_data(function):
    """Get buffer data using specified function."""
    channels = range(1, 3)
    start_bins = range(16383)
    bins = range(1, 16384)

    # add some data to the buffer
    lia.trigger_start_mode = 0
    lia.end_of_buffer_mode = 0
    lia.sample_rate = 13
    lia.data_transfer_mode = 0
    lia.reset_data_buffers()
    lia.start()
    time.sleep(0.5)
    lia.pause()
    buffer_size = lia.buffer_size

    for channel in channels:
        # read a random sample of data from the buffer
        buffer_start_bin = random.choice(range(buffer_size))
        assert buffer_start_bin in start_bins
        buffer_bins = buffer_size - buffer_start_bin
        assert buffer_bins in bins
        buffer = function(channel, buffer_start_bin, buffer_bins)
        assert len(buffer) == buffer_bins
        for datum in buffer:
            assert type(datum) is float

    # make sure invalid settings raise errors
    with pytest.raises(ValueError):
        new_channel = max(channels) + 1
        buffer_start_bin = random.choice(range(buffer_size))
        assert buffer_start_bin in start_bins
        buffer_bins = buffer_size - buffer_start_bin
        assert buffer_bins in bins
        buffer = function(new_channel, buffer_start_bin, buffer_bins)
    with pytest.raises(ValueError):
        new_channel = random.choice(channels)
        buffer_start_bin = max(start_bins) + 1
        buffer_bins = buffer_size - buffer_start_bin
        buffer = function(new_channel, buffer_start_bin, buffer_bins)
    with pytest.raises(ValueError):
        new_channel = random.choice(channels)
        buffer_start_bin = random.choice(range(buffer_size))
        assert buffer_start_bin in start_bins
        buffer_bins = max(bins) + 1
        buffer = lia.get_ascii_buffer_data(new_channel, buffer_start_bin, buffer_bins)

    lia.reset_data_buffers()


def test_get_ascii_buffer_data():
    """Test get ascii buffer data function."""
    _get_buffer_data(lia.get_ascii_buffer_data)


def test_get_binary_buffer_data():
    """Test get ascii buffer data function."""
    _get_buffer_data(lia.get_binary_buffer_data)


def test_get_non_norm_buffer_data():
    """Test get ascii buffer data function."""
    _get_buffer_data(lia.get_non_norm_buffer_data)


def test_idn():
    """Test identity property."""
    idn_format = "Stanford_Research_Systems,SR830,s/n00111,ver1.000"
    idn = lia.idn
    assert type(idn) is str
    assert len(idn) == len(idn_format)
    assert len(idn.split(",")) == len(idn_format.split(","))
    assert idn.split(",")[0] == idn_format.split(",")[0]
    assert idn.split(",")[1] == idn_format.split(",")[1]


def test_local_mode():
    """Test read/write local mode property."""
    settings = range(3)
    _int_property_test(settings, lia.local_mode)


def test_gpib_override_remote():
    """Test read/write gpib override property."""
    settings = range(2)
    _int_property_test(settings, lia.gpib_override_remote)


def test_clear_status_registers():
    """Test clear status registers."""
    lia.clear_status_registers()


def test_power_on_status_clear_bit():
    """Test power on status clear bit property."""
    settings = range(2)
    _int_property_test(settings, lia.power_on_status_clear_bit)


def test_disconnect():
    """Test for successful disconnection."""
    lia.disconnect()
    with pytest.raises(visa.InvalidSession):
        lia.instr.session
