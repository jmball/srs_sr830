"""Fresh fake VISA resources for each unit test; never open hardware."""

from types import SimpleNamespace
from unittest.mock import Mock

import pyvisa
from pyvisa.constants import InterfaceType
from pyvisa.resources import GPIBInstrument, SerialInstrument
import pytest

from sr830 import SR830
from virtual_sr830 import VirtualSR830


@pytest.fixture
def driver():
    return SR830()


@pytest.fixture
def resource():
    return Mock(spec=SerialInstrument)


@pytest.fixture
def gpib_resource():
    return Mock(spec=GPIBInstrument)


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
def simulation():
    """Fresh, connected simulator with deterministic time and guaranteed cleanup."""
    with VirtualSR830(clock=lambda: 0.0) as instrument:
        instrument.connect("GPIB0::8::INSTR")
        yield instrument


@pytest.fixture
def query_replies(resource):
    """Map exact VISA queries to replies; unexpected queries fail immediately.

    Use this for steady settings, rather than depending on incidental query order.
    Keep side_effect sequences for tests that deliberately model changing replies.
    """
    replies = {}
    resource.query.side_effect = replies.__getitem__
    return replies
