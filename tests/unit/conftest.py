"""Fresh fake VISA resources for each unit test; never open hardware."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import pyvisa
from pyvisa.constants import InterfaceType
from pyvisa.resources import GPIBInstrument, SerialInstrument

from sr830 import SR830
from tests.support import ManualClock
from virtual_sr830 import VirtualSR830


@pytest.fixture
def driver():
    return SR830()


@pytest.fixture
def resource():
    resource = Mock(spec=SerialInstrument)
    resource.query.return_value = "0"
    resource.interface_type = InterfaceType.asrl
    return resource


@pytest.fixture
def gpib_resource():
    resource = Mock(spec=GPIBInstrument)
    resource.query.return_value = "0"
    resource.interface_type = InterfaceType.gpib
    return resource


@pytest.fixture
def manager(resource):
    manager = Mock(spec=pyvisa.ResourceManager)
    manager.resource_info.return_value = SimpleNamespace(
        interface_type=InterfaceType.asrl
    )
    manager.open_resource.return_value = resource
    return manager


@pytest.fixture
def connect(driver, manager):
    def connect_resource(**kwargs):
        driver.connect("alias", resource_manager=manager, **kwargs)

    return connect_resource


@pytest.fixture
def mock_instrument(driver, resource):
    """An attached fake resource for command tests (not a hardware connection)."""
    driver._instr = resource
    return driver


@pytest.fixture
def simulation_clock(monkeypatch):
    """Replace internal time sources, keeping production's public API unchanged."""
    clock = ManualClock()
    timer = SimpleNamespace(monotonic=clock, sleep=clock.advance)
    for module in (
        "sr830.sr830",
        "virtual_sr830.virtual_sr830",
    ):
        monkeypatch.setattr(f"{module}.time", timer)
    return clock


@pytest.fixture
def simulation(simulation_clock):
    """Fresh, connected simulator with deterministic time and guaranteed cleanup."""
    with VirtualSR830() as instrument:
        instrument.connect()
        yield instrument


@pytest.fixture
def query_replies(resource):
    """Map exact VISA queries to replies; unexpected queries fail immediately.

    Use this for steady settings, rather than depending on incidental query order.
    Keep side_effect sequences for tests that deliberately model changing replies.
    """
    replies = {"*ESR?": "0", "ERRS?": "0", "LIAS?": "0"}
    resource.query.side_effect = replies.__getitem__
    return replies
