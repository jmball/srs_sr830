# srs_sr830
Control a Stanford Research Systems SR830 lock-in amplifier

## Installation

Requires Python 3.8 or newer. Install from the repository root:

```sh
python -m pip install .
```

For development, create a virtual environment and install in editable mode:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Package metadata, dependencies, and build configuration are in `pyproject.toml`.
The distribution installs both `sr830` and `virtual_sr830`. Hardware access
requires an appropriate VISA backend and a connected instrument.
