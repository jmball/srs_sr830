from importlib.metadata import PackageNotFoundError, version

# get version if package has been installed
try:
    __version__ = version("srs_sr830")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .virtual_sr830 import *
