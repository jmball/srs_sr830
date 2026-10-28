"""Pytest options and fixtures for virtual or explicitly selected hardware tests."""

import time

import pytest

from sr830 import EndOfBufferMode, ReferenceSource, SampleRate, TriggerStartMode
from tests.support import (
    InstrumentOptions,
    open_instrument,
    positive_float,
    positive_int,
    preserve_settings,
)


def pytest_addoption(parser):
    group = parser.getgroup("SR830 instrument testing")
    group.addoption(
        "--resource-name",
        metavar="VISA_RESOURCE",
        help="Use this real SR830; default: VirtualSR830.",
    )
    group.addoption(
        "--visa-backend",
        metavar="BACKEND",
        help="PyVISA backend/library, for example @py.",
    )
    group.addoption(
        "--output-interface",
        type=int,
        choices=(0, 1),
        help="Instrument response interface: 0=RS232, 1=GPIB. Required for ambiguous adapters.",
    )
    group.addoption(
        "--visa-timeout",
        type=positive_int,
        default=5000,
        metavar="MS",
        help="VISA I/O timeout in milliseconds (default: 5000).",
    )
    group.addoption(
        "--baud-rate",
        type=positive_int,
        metavar="BAUD",
        help="Serial baud rate; must match the instrument.",
    )
    group.addoption(
        "--data-bits",
        type=int,
        choices=(8,),
        help="Serial data bits; the SR830 requires 8.",
    )
    group.addoption(
        "--parity",
        choices=("none", "odd", "even", "mark", "space"),
        help="Serial parity; must match the instrument.",
    )
    group.addoption(
        "--stop-bits",
        type=float,
        choices=(1, 1.5, 2),
        help="Serial stop bits; must match the instrument.",
    )
    group.addoption(
        "--write-termination",
        choices=("LF", "CR", "CRLF"),
        help="Command termination (default: driver LF).",
    )
    group.addoption(
        "--acquisition-timeout",
        type=positive_float,
        default=10.0,
        metavar="SECONDS",
        help="Maximum wait for hardware buffer samples (default: 10).",
    )


def pytest_report_header(config):
    resource = config.getoption("resource_name")
    return f"SR830 integration backend: {resource or 'VirtualSR830 (no hardware)'}"


def pytest_collection_modifyitems(config, items):
    for item in items:
        parts = item.path.relative_to(config.rootpath).parts
        section = parts[1] if len(parts) > 1 and parts[0] == "tests" else ""
        if section in ("unit", "integration"):
            item.add_marker(getattr(pytest.mark, section))
        if section == "integration" and config.getoption("resource_name"):
            item.add_marker(pytest.mark.hardware)


@pytest.fixture(scope="session")
def instrument_options(pytestconfig):
    names = InstrumentOptions.__dataclass_fields__
    return InstrumentOptions(**{name: pytestconfig.getoption(name) for name in names})


@pytest.fixture
def instrument(instrument_options):
    """Fresh connection per test, closed even on test/setup failure; never reset."""
    with open_instrument(instrument_options) as connected:
        yield connected


@pytest.fixture
def internal_reference(instrument):
    # Frequency is writable only in internal-reference mode on real hardware.
    with preserve_settings(instrument, "reference_source"):
        instrument.reference_source = ReferenceSource.INTERNAL
        # FREQ? in external mode reports the measured frequency, which may be
        # zero if unlocked. Capture the stored internal frequency after switching.
        with preserve_settings(instrument, "reference_frequency"):
            yield instrument


@pytest.fixture
def recorded_instrument(instrument, pytestconfig):
    """Acquire four points using the same interface on hardware and simulation."""
    with preserve_settings(
        instrument,
        "sample_rate",
        "end_of_buffer_mode",
        "trigger_start_mode",
        "data_transfer_mode",
    ):
        instrument.pause()
        instrument.reset_data_buffers()
        instrument.end_of_buffer_mode = EndOfBufferMode.ONE_SHOT
        instrument.trigger_start_mode = TriggerStartMode.OFF
        instrument.data_transfer_mode = 0
        instrument.sample_rate = SampleRate.Hz_16
        try:
            instrument.start()
            deadline = time.monotonic() + pytestconfig.getoption("acquisition_timeout")
            while instrument.buffer_size < 4:
                if time.monotonic() >= deadline:
                    pytest.fail(
                        "SR830 did not acquire four buffer samples before --acquisition-timeout."
                    )
                time.sleep(0.05)
            instrument.pause()
            yield instrument
        finally:
            instrument.pause()
