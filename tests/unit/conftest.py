"""Fresh fake VISA resources for each unit test; never open hardware."""

from types import SimpleNamespace
from unittest.mock import Mock

import pyvisa
from pyvisa.constants import InterfaceType
from pyvisa.resources import SerialInstrument
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
def virtual():
    return VirtualSR830()
