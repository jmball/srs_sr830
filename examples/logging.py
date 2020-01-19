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
instr = sr830.sr830(address="ASRL2::INSTR", output_interface=0)

# log device info
sn = instr.serial_number
logger.info(
    f"{instr.manufacturer}, {instr.model}, {sn}, {instr.firmware_version} connected!"
)

# query something and log formatted response
resp_dict = instr.get_ref_freq()
freq = resp_dict["fmt_resp"]
logger.info(f"{sn}, ref frequency = {freq} Hz")

# log query, response, and error info
logger.debug(
    f"{sn}, cmd: {resp_dict['cmd']}, resp: {resp_dict['resp']}, err_code: {resp_dict['err_code']}, err_msg: {resp_dict['err_msg']}"
)

# close VISA resource
instr.instr.close()
