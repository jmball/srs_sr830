# srs_sr830
Control a Stanford Research Systems SR830 lock-in amplifier

## Installation

Requires Python 3.10 or newer. Install from the repository root:

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

## Connections

```python
import sr830

with sr830.sr830() as instrument:
    instrument.connect("ASRL2::INSTR", baud_rate=9600)
    print(instrument.reference_frequency)
```

`connect()` infers RS232 for ASRL resources and GPIB for GPIB resources, including
adapters exposed as those VISA types. For TCP/IP and other ambiguous resources,
specify the adapter's instrument-side interface explicitly:

```python
instrument.connect("TCPIP0::adapter.example::1234::SOCKET", output_interface=1)
```

Use `output_interface=0` for an Ethernet-to-serial adapter and `1` for
Ethernet-to-GPIB. An explicit value overrides inference. TCP/IP resource names
alone cannot establish the downstream interface; the adapter must already be
configured to forward SR830 commands and responses. Adapter-specific addressing
or controller commands are outside this driver's scope.

The driver requires CR (`"\r"`) response termination for RS232 and LF (`"\n"`)
for GPIB. It defaults command termination to LF and rejects conflicting framing
before opening the resource. Serial also accepts CR or CRLF commands; GPIB
accepts CRLF, and native GPIB VISA resources can use EOI alone with
`write_termination=None` and `send_end=True`. Serial baud rate and parity must
match the instrument's front-panel settings.

All connection options after the resource name are keyword-only. Connection
selects the output interface, enables status registers, and enters remote mode
with front-panel lockout by default; use `local_lockout=False` to allow the Local
key. It preserves measurement settings and does not reset the instrument. Call
`instrument.reset()` explicitly when wanted; `reset=` is no longer accepted by
`connect()`.

Initialization failures close the opened resource and leave `instrument.instr`
as `None`. Commands already sent cannot be rolled back. Calling `connect()` on
an already connected instance raises `RuntimeError`; call `disconnect()` first.
Disconnect returns the instrument to local mode, closes its resource, clears
`instr`, and tolerates repeated calls.

Pass `resource_manager=` to use an existing PyVISA manager. The driver retains
that manager throughout the connection. Caller-supplied managers remain
caller-owned; the driver closes only its instrument resource. It also leaves
default managers open because PyVISA shares managers and backend sessions across
connections. Close managers at the application level when all their resources
are finished. The virtual driver accepts the same connection options without
opening hardware.

Both packages ship inline type hints. `measure_multiple()` returns an iterator
of floats; buffer readers return tuples. The virtual status-register getters
remain unimplemented and return `None`.

Hardware-free connection tests can be run with:

```sh
python -m unittest discover -s tests
```
