"""Log identification and reference frequency from a real serial instrument."""
import logging
import sys

import sr830


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s|%(name)s|%(levelname)s|%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)
    with sr830.sr830() as instrument:
        # Match baud rate and parity to the instrument's front-panel settings.
        instrument.connect("ASRL2::INSTR", baud_rate=9600)
        logger.info("Connected: %s", instrument.idn)
        logger.info("Reference frequency = %s Hz", instrument.reference_frequency)


if __name__ == "__main__":
    main()
