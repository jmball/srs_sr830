"""Invalid public inputs fail before VISA I/O; integer codes are never coerced."""

import pytest

from tests.cases import SETTING_COMMANDS


@pytest.mark.parametrize("value", [1.5, 1.0, True, "1"])
@pytest.mark.parametrize("name,enum,command", SETTING_COMMANDS)
def test_integer_setting_codes_reject_coercion(
    mock_instrument, resource, name, enum, command, value
):
    with pytest.raises(ValueError):
        setattr(mock_instrument, name, value)
    resource.write.assert_not_called()
    resource.query.assert_not_called()


@pytest.mark.parametrize("value", [1.5, 1.0, True, "1"])
@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(lambda d, v: setattr(d, "harmonic", v), id="harmonic"),
        pytest.param(lambda d, v: d.save_setup(v), id="save-slot"),
        pytest.param(lambda d, v: d.recall_setup(v), id="recall-slot"),
        pytest.param(lambda d, v: d.set_enable_register("error", v), id="register-mask"),
        pytest.param(lambda d, v: d.get_enable_register("error", v), id="enable-bit"),
        pytest.param(lambda d, v: d.get_status_byte("error", v), id="status-bit"),
        pytest.param(lambda d, v: d.get_ascii_buffer_data(1, v, 1), id="trace-start"),
        pytest.param(lambda d, v: d.get_ascii_buffer_data(1, 0, v), id="trace-count"),
    ],
)
def test_integer_arguments_reject_coercion(mock_instrument, resource, operation, value):
    with pytest.raises(ValueError):
        operation(mock_instrument, value)
    resource.write.assert_not_called()
    resource.query.assert_not_called()


@pytest.mark.parametrize("bits", [5, 6, 7, 8.0, True])
def test_serial_requires_eight_bits_before_open(connect, manager, bits):
    with pytest.raises(ValueError, match="data_bits=8"):
        connect(data_bits=bits)
    manager.open_resource.assert_not_called()


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        pytest.param("set_display", (0, 0), {}, id="display-channel"),
        pytest.param("set_display", (1, 5), {}, id="display-code"),
        pytest.param("set_display", (1, 0, 3), {}, id="ratio-code"),
        pytest.param("get_display", (3,), {}, id="get-display-channel"),
        pytest.param("set_front_output", (0, 0), {}, id="front-output-channel"),
        pytest.param("set_front_output", (1, 2), {}, id="front-output-code"),
        pytest.param("get_front_output", (3,), {}, id="get-front-output-channel"),
        pytest.param("set_output_offset_expand", (1, -106, 0), {}, id="offset-low"),
        pytest.param("set_output_offset_expand", (1, 106, 0), {}, id="offset-high"),
        pytest.param("set_output_offset_expand", (1, 0, 3), {}, id="expansion-code"),
        pytest.param("get_aux_in", (0,), {}, id="aux-input-channel"),
        pytest.param("set_aux_out", (5, 0), {}, id="aux-output-channel"),
        pytest.param("set_aux_out", (1, -11), {}, id="aux-voltage-low"),
        pytest.param("set_aux_out", (1, 11), {}, id="aux-voltage-high"),
        pytest.param("get_aux_out", (0,), {}, id="get-aux-output-channel"),
        pytest.param("save_setup", (0,), {}, id="save-slot-low"),
        pytest.param("save_setup", (10,), {}, id="save-slot-high"),
        pytest.param("recall_setup", (0,), {}, id="recall-slot-low"),
        pytest.param("recall_setup", (10,), {}, id="recall-slot-high"),
        pytest.param("read_display", (0,), {}, id="read-display-channel"),
        pytest.param("measure_multiple", ([],), {}, id="snapshot-empty"),
        pytest.param("measure_multiple", ([1],), {}, id="snapshot-too-short"),
        pytest.param(
            "measure_multiple", ([1, 2, 3, 4, 5, 6, 7],), {}, id="snapshot-too-long"
        ),
        pytest.param("measure_multiple", ([0, 1],), {}, id="snapshot-code-low"),
        pytest.param("measure_multiple", ([1, 12],), {}, id="snapshot-code-high"),
        pytest.param(
            "get_ascii_buffer_data", (1, 0, 1), {"resume": 1}, id="resume-not-bool"
        ),
        pytest.param(
            "get_enable_register", ("unknown",), {}, id="enable-register-name"
        ),
        pytest.param("get_status_byte", ("unknown",), {}, id="status-register-name"),
        pytest.param("set_enable_register", ("unknown", 0), {}, id="set-register-name"),
        pytest.param(
            "set_enable_register", ("error", 0), {"decimal": 1}, id="decimal-not-bool"
        ),
        pytest.param("set_enable_register", ("error", None), {}, id="register-mask-none"),
        pytest.param("set_enable_register", ("error", -1), {}, id="register-mask-low"),
        pytest.param(
            "set_enable_register", ("error", 256), {}, id="register-mask-high"
        ),
        pytest.param(
            "set_enable_register",
            ("error", 2),
            {"decimal": False, "bit": 0},
            id="register-bit-value",
        ),
        pytest.param(
            "set_enable_register",
            ("error", 1),
            {"decimal": False},
            id="register-bit-required",
        ),
        pytest.param("get_enable_register", ("error", -1), {}, id="enable-bit-low"),
        pytest.param("get_status_byte", ("error", 8), {}, id="status-bit-high"),
        pytest.param("read_fast_data", (0,), {}, id="fast-sample-count"),
    ],
)
def test_invalid_arguments_fail_before_io(
    mock_instrument, resource, method, args, kwargs
):
    with pytest.raises(ValueError):
        getattr(mock_instrument, method)(*args, **kwargs)
    resource.write.assert_not_called()
    resource.query.assert_not_called()
    resource.read_bytes.assert_not_called()


@pytest.mark.parametrize("value", [0, 20000])
def test_harmonic_out_of_range_fails_before_io(mock_instrument, resource, value):
    with pytest.raises(ValueError):
        mock_instrument.harmonic = value
    resource.write.assert_not_called()
