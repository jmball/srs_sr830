"""Buffer acquisition/readout shared by hardware and the stateful simulator."""

import math
import pytest

from sr830 import Channel


@pytest.mark.parametrize(
    "reader_name",
    [
        "get_ascii_buffer_data",
        "get_binary_buffer_data",
        "get_non_norm_buffer_data",
    ],
)
@pytest.mark.parametrize("channel", list(Channel))
def test_buffer_read(recorded_instrument, reader_name, channel):
    values = getattr(recorded_instrument, reader_name)(channel, 0, 4)
    assert isinstance(values, tuple)
    assert len(values) == 4
    assert all(math.isfinite(value) for value in values)
