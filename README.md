# srs_sr830
Control a Stanford Research Systems SR830 lock-in amplifier

## Installation

Requires Python 3.10 or newer. Install [uv](https://docs.astral.sh/uv/getting-started/installation/),
then run from the repository root:

```sh
uv sync --locked
```

uv creates `.venv`, installs the project in editable mode, and installs the
`dev` dependency group (pytest, coverage, and mypy). Run commands with `uv run`;
activating the environment is optional. Commit `uv.lock` when dependencies change.

For a runtime-only environment, use `uv sync --locked --no-dev`. Native serial
access through the Python VISA backend is available with the `serial` extra:

```sh
uv sync --locked --extra serial
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
match the instrument's front-panel settings. RS232 always uses 8 data bits;
conflicting `data_bits` values are rejected.

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
of floats; buffer readers return tuples. Integer protocol fields reject floats
and booleans rather than silently coercing them.

## Configuration and measurement examples

Both examples show connection, configuration, settling, and coherent X/Y/R/phase
measurements inline in `main()`.

Run [the virtual example](examples/configure_and_measure_virtual.py) without
hardware:

```sh
uv run --locked python examples/configure_and_measure_virtual.py
```

It supplies simulated 3 mV X and 4 mV Y RMS components. Waiting for settling
advances simulated time without sleeping.

[The hardware example](examples/configure_and_measure.py) requires an explicit
VISA resource. It changes reference source, harmonic and frequency, input
configuration, sensitivity, time constant, filter slope, and reserve mode; connect
a suitable signal source before running. It selects the fundamental harmonic,
137 Hz internal reference, 10 mV sensitivity, normal reserve, 12 dB/octave slope,
and a 100 ms time constant, then waits an estimated ten time constants.

```sh
uv run --locked python examples/configure_and_measure.py \
    --resource-name "GPIB0::8::INSTR"

uv run --locked --extra serial python examples/configure_and_measure.py \
    --resource-name "ASRL2::INSTR" --baud-rate 9600
```

Use `--output-interface 0` or `1` for ambiguous adapters, and `--visa-backend @py`
to select PyVISA-py. Run the hardware example with `--help` for all options.

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
`LiaStatusBit`/`LiaStatusFlag`. Both drivers implement enable registers, event
registers, and serial-poll status. Reading event registers clears the queried
events; `serial_poll()` performs native VISA polling and acknowledges SRQ.

The enums are the public representation of discrete settings; legacy value
and description tables have been removed. Member meanings, physical units,
and instrument command codes are documented in their enum docstrings.
Setters accept enum members or integer command codes, not physical values.
See the [SR830 programming manual](https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf)
for instrument codes and units.

## Acquisition and completion

Buffer readers validate the range against the 16383-point capacity and the
number of acquired samples. ASCII and binary reads reject incomplete responses.
Loop scans are paused before reading and **remain paused by default**. Pass
`resume=True` to restart with `STRT` after a successful read; failed reads leave
acquisition paused. The instrument cannot reliably report whether an existing
scan is paused, so this is an explicit policy rather than an inferred restoration.
One-shot scans are not automatically paused or restarted.

`wait_until_ready(timeout=10)` waits for command completion, using native VISA
status polling where supported and a queued query otherwise. `wait_for_settling(
timeout=60, time_constants=10)` additionally waits the requested multiple of the
selected low-pass time constant. Both use seconds and raise `TimeoutError` when
the budget is insufficient. Settling is an estimate, not a stability measurement
or a model of external reference locking and synchronous-filter transients.

GPIB FAST transfers have a dedicated reader:

```python
from sr830 import DataTransferMode, SampleRate

instrument.sample_rate = SampleRate.Hz_64
instrument.data_transfer_mode = DataTransferMode.WINDOWS
instrument.start()  # STRD provides the instrument's 0.5-second startup delay.
try:
    xy_counts = instrument.read_fast_data(32, timeout=2)
finally:
    instrument.pause()
```

Each pair contains signed 16-bit X/Y counts. Before offset and expansion,
±30000 corresponds to the selected full scale; FAST counts include both offset
and expansion. FAST is GPIB only. Read promptly: FAST2 has room for only 63 pairs.
Text queries are blocked while the driver tracks an active FAST stream. Pausing
stops acquisition and uses VISA device clear to discard unread stream bytes
before text I/O resumes; a failed clear keeps that guard active. A failed FAST
read attempts the same cleanup. Resetting the buffers, resetting the instrument,
or disabling FAST also clears pending stream bytes.

## Simulation

`VirtualSR830` inherits the hardware driver's settings, validation, and command
methods. Its in-memory protocol model provides coherent X/Y/R/phase readings,
cascaded low-pass settling, offsets, display ratios, independent auxiliary inputs
and outputs, auto functions, saved setups, status registers, triggered and timed
acquisition, bounded circular buffers, all three trace encodings, and FAST counts.
Reset preserves the response interface and status registers, as on the instrument.

```python
from virtual_sr830 import VirtualSR830
from sr830 import MeasurementParameter, SampleRate, TimeConstant

with VirtualSR830(clock=lambda: 0.0) as instrument:
    instrument.connect("GPIB0::8::INSTR")  # No VISA resource is opened.
    instrument.time_constant = TimeConstant.ms_100
    instrument.set_signal(0.003, 0.004)  # Demodulated RMS X/Y in V.
    instrument.wait_for_settling()      # Advances simulation time, no sleep.
    print(tuple(instrument.measure_multiple([
        MeasurementParameter.X, MeasurementParameter.Y, MeasurementParameter.R,
    ])))
    instrument.sample_rate = SampleRate.Hz_16
    instrument.start()
    instrument.advance_time(0.25)
    trace = instrument.get_ascii_buffer_data(1, 0, 4)
```

The default clock follows monotonic wall time. An injected clock plus
`advance_time(seconds)` makes experiments deterministic and fast. Constructor
`signal=lambda seconds: complex(x, y)` provides a time-dependent input, evaluated
at simulation updates and acquisition sample times. Constant-input changes have
an analytic cascaded-filter step response; varying callbacks use a stepwise input
approximation, so advance in small increments for rapid waveforms. `set_signal()`
replaces the callback; `settle=True` initializes the filter immediately.

Signals are demodulated RMS amplitudes in V for voltage mode and A for current
mode, before phase, offset, and expansion. `set_aux_input(channel, voltage)` and
`set_external_reference(frequency, locked=True)` supply external conditions;
`inject_status(register, mask)` supplies faults for application tests. Configuration
survives disconnect/reconnect, while I/O requires a connection.

This models an ideal demodulated signal, not the analog front end: notch filters,
AC coupling, synchronous rejection, input noise, calibration, overload distortion,
and reserve-dependent interference are not electrically simulated. Noise displays
read zero for the ideal input, and auto reserve selects low noise. The signal
callback can supply demodulated interference or noise to test application behavior.
Simulation does not validate VISA transport, adapter firmware, or physical accuracy.

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
The [logging example](examples/connect_with_logging.py) configures output and warning capture
at the application level.

## Testing

Run the tests using the locked development environment:

```sh
uv sync --locked
uv run --locked pytest
```

`tests/unit/` uses fake VISA resources. `tests/integration/` exercises the public
interface, including acquisition and registers, on `VirtualSR830` by default.
To run the integration tests against a real instrument:

```sh
uv run --locked --extra serial pytest tests/integration --resource-name "ASRL2::INSTR" \
    --visa-backend=@py --baud-rate 9600 --data-bits 8 --parity none --stop-bits 1
```

For adapters whose instrument-side interface is ambiguous, supply
`--output-interface 0` (RS232) or `--output-interface 1` (GPIB). Use
`--visa-backend=@py` with the equals sign because pytest interprets standalone
`@...` arguments as argument files. `uv run --locked pytest --help` lists all options.

Hardware runs temporarily change settings and outputs, and buffer tests pause
acquisition and clear existing buffers. Changed properties are restored on exit;
previous acquisition data and scan activity cannot be restored. See the
[test guide](tests/README.md) for the layout, hardware options, and limitations.

```sh
uv run --locked pytest -m unit
uv run --locked pytest --cov --cov-report=term-missing
```

Type-check and build distributions with:

```sh
uv run --locked mypy --python-version 3.10 --strict --follow-imports=silent \
    src/sr830/settings.py src/sr830/sr830.py src/sr830/_connection.py \
    src/virtual_sr830/virtual_sr830.py src/virtual_sr830/_simulation.py
uv build
```

Use `uv add <package>` for runtime dependencies, `uv add --dev <package>` for
development tools, and `uv lock --upgrade-package <package>` for a targeted
lockfile update. `uv sync --locked` verifies that the lockfile matches
`pyproject.toml` before installing it.
