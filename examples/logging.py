"""Logging example."""

import logging
import sys

import sr830

# set up logger
console_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s|%(name)s|%(levelname)s|%(message)s",
    handlers=[console_handler],
)
logger = logging.getLogger()

# instantiate object
instr = sr830.sr830()
instr.connect(resource_name="ASRL2::INSTR", output_interface=0)

# log device info
sn = instr.serial_number
logger.info(
    f"{instr.manufacturer}, {instr.model}, {sn}, {instr.firmware_version} connected!"
)

# query something and log formatted response
freq = instr.get_ref_freq()
logger.info(f"{sn}, ref frequency = {freq} Hz")

# close VISA resource
instr.disconnect()
