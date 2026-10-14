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
The distribution installs both `sr830` and `virtual_sr830`. The classes are
`sr830.SR830` and `virtual_sr830.VirtualSR830`. Hardware access
requires an appropriate VISA backend and a connected instrument.

## Connections

```python
import sr830

with sr830.SR830() as instrument:
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
selects the output interface and enables status registers. Set `local_mode`
explicitly after connecting to select local (`0`), remote (`1`), or local lockout
(`2`):

```python
instrument.connect("ASRL2::INSTR")
instrument.local_mode = 2  # Disable the front-panel Local key.
```

GPIB commands can still put the instrument into remote mode automatically.
Connection preserves measurement settings and does not reset the instrument.
Call `instrument.reset()` explicitly when wanted.

Initialization failures close the opened resource and leave the instance
disconnected. Commands already sent cannot be rolled back. Calling `connect()` on
an already connected instance raises `RuntimeError`; call `disconnect()` first.
Disconnect returns the instrument to local mode, closes its resource, clears
the connection, and tolerates repeated calls.

Pass `resource_manager=` to use an existing PyVISA manager. The VISA resource
retains that manager throughout the connection. Caller-supplied managers remain
caller-owned; the driver closes only its instrument resource. It also leaves
default managers open because PyVISA shares managers and backend sessions across
connections. Close managers at the application level when all their resources
are finished. The virtual driver accepts the same connection options without
opening hardware.

Both packages ship inline type hints. `measure_multiple()` returns an iterator
of floats; buffer readers return tuples. The virtual status-register getters
remain unimplemented and return `None`.

## Named settings

Discrete settings accept their named enums or the existing integer codes. Enum
values are instrument command codes, not physical values. Getters continue to
return integer codes; construct the enum from a getter when a named result is
wanted. Enum inputs must belong to the setting being used; an unrelated enum is
rejected even when its number is in range.

```python
from sr830 import (
    LowPassFilterSlope, SampleRate, Sensitivity, TimeConstant, SR830,
)

with SR830() as instrument:
    instrument.connect("ASRL2::INSTR")
    instrument.sensitivity = Sensitivity.x1u
    instrument.time_constant = TimeConstant.ms_100
    instrument.lowpass_filter_slope = LowPassFilterSlope.dB_12
    instrument.sample_rate = SampleRate.Hz_512

    selected = Sensitivity(instrument.sensitivity)
    # selected is Sensitivity.x1u: full scale is 1 microvolt or 1 picoamp.
```

Unit-valued settings use `<unit>_<value>` (for example, `ms_100`, `dB_12`,
and `Hz_512`). Multiplier settings use `x<value>` (for example, `x10` and
`x1u`). An underscore replaces a decimal point in `SampleRate.mHz_62_5`.

Sensitivity names use `x<number><SI prefix>`, with `u` for micro. The `x`
indicates a full-scale amplitude multiplier applied to V for voltage inputs or
microamps for current inputs, not amplifier gain. `Sensitivity.x1` is the unity
multiplier (1 V or 1 microamp).

| Setting enum | Example | Instrument code | Meaning |
| --- | --- | --- | --- |
| `Sensitivity` | `x1u` | 8 | 1 microvolt or 1 picoamp full scale |
| `Sensitivity` | `x200m` | 24 | 200 millivolts or 200 nanoamps full scale |
| `Sensitivity` | `x1` | 26 | 1 volt or 1 microamp full scale |
| `TimeConstant` | `ms_100` | 8 | 100 milliseconds |
| `LowPassFilterSlope` | `dB_12` | 1 | 12 dB/octave |
| `OutputExpansion` | `x1`, `x10`, `x100` | 0, 1, 2 | Output expansion factors |
| `SampleRate` | `mHz_62_5`, `Hz_512`, `TRIGGER` | 0, 13, 14 | Rate in Hz or triggered sampling |

The enum types are defined in `sr830.settings` and exported by both `sr830` and
`virtual_sr830`. Existing categorical enums cover reference source/trigger,
input configuration, grounding/coupling, filters, reserve mode, channel
displays/ratios, output source/interface, on/off settings, buffer/trigger modes,
data transfer, and local mode.

Selectors are named too: `Channel.CH1`, `AuxiliaryChannel.AUX4`,
`OutputParameter.R`, and `MeasurementParameter.PHASE`. `measure()` accepts only
X, Y, R, and PHASE; `measure_multiple()` also accepts the auxiliary inputs,
reference frequency, and channel displays. Display and ratio enums must match
the channel passed to `set_display()`.

```python
from sr830 import (
    Channel, Channel1Display, Channel1Ratio, MeasurementParameter,
    OutputExpansion, OutputParameter,
)

instrument.set_display(Channel.CH1, Channel1Display.R, Channel1Ratio.NONE)
instrument.set_output_offset_expand(OutputParameter.R, 0.0, OutputExpansion.x10)
values = tuple(instrument.measure_multiple([
    MeasurementParameter.X, MeasurementParameter.Y,
]))
```

Register selectors retain their string values through `StatusRegister`. Each
register has a separate `*Bit` enum of bit positions and `*Flag` enum of masks.
Use positions for `bit=`, and combine masks with `|` for whole-byte operations.
Both types must match the selected register. Integer bits/masks and string
register names remain accepted.

```python
from sr830 import ErrorBit, ErrorFlag, StatusRegister, SwitchState

instrument.set_enable_register(
    StatusRegister.ERROR, ErrorFlag.RAM_ERROR | ErrorFlag.ROM_ERROR,
)
instrument.set_enable_register(
    StatusRegister.ERROR, SwitchState.ON,
    decimal=False, bit=ErrorBit.RAM_ERROR,
)
errors = ErrorFlag(instrument.get_status_byte(StatusRegister.ERROR))
```

The four position/mask pairs are `StandardEventBit`/`StandardEventFlag`,
`SerialPollBit`/`SerialPollFlag`, `ErrorBit`/`ErrorFlag`, and
`LiaStatusBit`/`LiaStatusFlag`. Virtual register getters remain unimplemented
and return `None`.

The enums are the public representation of discrete settings; legacy value
and description tables have been removed. Member meanings, physical units,
and instrument command codes are documented in their enum docstrings.
Setters accept enum members or integer command codes, not physical values.
See the [SR830 programming manual](https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf)
for instrument codes and units.

## Logging and warnings

The driver uses the `sr830.sr830` logger with a `NullHandler`. Applications
choose handlers, formatting, and levels. Enable `DEBUG` for connection setup
and disconnection diagnostics; ordinary measurements are not logged.

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("sr830").setLevel(logging.DEBUG)
```

The driver does not change global warning handling. Applications can call
`logging.captureWarnings(True)` if they want Python warnings routed into logging.
Serial binary-transfer warnings identify the caller's location and can also be
handled through the standard `warnings` module.

`instrument.errors` returns an error list without printing, logging, or issuing
warnings. The application chooses how to report it:

```python
errors = instrument.errors
if errors:
    logging.getLogger(__name__).warning("Instrument reported errors: %s", ", ".join(errors))
```

Reading `errors` queries status registers and can clear their latched events;
see the [SR830 status-register documentation](https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf).
The [logging example](examples/logging.py) configures output and warning capture
at the application level.

Hardware-free connection, settings, and logging tests can be run with:

```sh
python -m unittest discover -s tests
```
