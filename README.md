# srs_sr830
Control a Stanford Research Systems SR830 lock-in amplifier

## Installation

Requires Python 3.10 or newer. Install [uv](https://docs.astral.sh/uv/getting-started/installation/),
then run from the repository root:

```sh
uv sync --locked
```

uv creates `.venv`, installs the project in editable mode, and installs the
`dev` dependency group (pytest, coverage, ty, and Ruff). Run commands with `uv run`;
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

Both examples show connection, reference/input/filter/control settings,
acquisition choices, display and front-output selection, auxiliary outputs, and
status enable masks inline in `main()`, followed by settling and coherent
X/Y/R/phase measurements. The hardware example puts its command-line options in
`parse_args()` and defaults to the PyVISA-py backend (`@py`).

Run [the virtual example](examples/configure_and_measure_virtual.py) without
hardware:

```sh
uv run --locked python examples/configure_and_measure_virtual.py
```

It supplies a simulated 5 mV RMS input at 30 degrees. Settling and acquisition
follow elapsed time, with the same waits as the hardware driver.

[The hardware example](examples/configure_and_measure.py) requires an explicit
VISA resource. It changes reference, input, filter, front-panel, and acquisition
settings; connect a suitable signal source before running. It selects the
fundamental harmonic, 137 Hz internal reference, 10 mV sensitivity, normal
reserve, 12 dB/octave slope, and a 100 ms time constant, then waits an estimated
ten time constants. Display channels use R and phase with no ratio, output
expansion stays at unity with zero offset, auxiliary outputs are set to zero,
and FAST transfer remains off. It also enables selected error-register events
and sets power-on status clearing.

```sh
uv run --locked python examples/configure_and_measure.py \
    --resource-name "GPIB0::8::INSTR"

uv run --locked --extra serial python examples/configure_and_measure.py \
    --resource-name "ASRL2::INSTR" --baud-rate 9600
```

Use `--output-interface 0` or `1` for ambiguous adapters. The default
`--visa-backend` is `@py` (PyVISA-py); pass another backend name to override it.
Run the hardware example with `--help` for all options.

## Named settings

Discrete settings accept their named enums or the existing integer codes. Enum
values are instrument command codes, not physical values. Getters continue to
return integer codes; construct the enum from a getter when a named result is
wanted. Enum inputs must belong to the setting being used; an unrelated enum is
rejected even when its number is in range.

```python
from sr830 import (
    LowPassFilterSlope,
    SampleRate,
    Sensitivity,
    TimeConstant,
    SR830,
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
    Channel,
    Channel1Display,
    Channel1Ratio,
    MeasurementParameter,
    OutputExpansion,
    OutputParameter,
)

instrument.set_display(Channel.CH1, Channel1Display.R, Channel1Ratio.NONE)
instrument.set_output_offset_expand(OutputParameter.R, 0.0, OutputExpansion.x10)
values = tuple(
    instrument.measure_multiple(
        [
            MeasurementParameter.X,
            MeasurementParameter.Y,
        ]
    )
)
```

Register selectors retain their string values through `StatusRegister`. Each
register has a separate `*Bit` enum of bit positions and `*Flag` enum of masks.
Use positions for `bit=`, and combine masks with `|` for whole-byte operations.
Both types must match the selected register. Integer bits/masks and string
register names remain accepted.

```python
from sr830 import ErrorBit, ErrorFlag, StatusRegister, SwitchState

instrument.set_enable_register(
    StatusRegister.ERROR,
    ErrorFlag.RAM_ERROR | ErrorFlag.ROM_ERROR,
)
instrument.set_enable_register(
    StatusRegister.ERROR,
    SwitchState.ON,
    decimal=False,
    bit=ErrorBit.RAM_ERROR,
)
errors = instrument.error_status  # ERRS?; returns ErrorFlag
```

The four position/mask pairs are `StandardEventBit`/`StandardEventFlag`,
`SerialPollBit`/`SerialPollFlag`, `ErrorBit`/`ErrorFlag`, and
`LiaStatusBit`/`LiaStatusFlag`. Both drivers implement enable registers, event
registers, and serial-poll status. Reading event registers clears the queried
events; `serial_poll()` performs native VISA polling and acknowledges SRQ.

Read-only status properties are available on both drivers:

```python
events = instrument.standard_event_status  # *ESR? -> StandardEventFlag
errors = instrument.error_status  # ERRS? -> ErrorFlag
lia_status = instrument.lia_status  # LIAS? -> LiaStatusFlag
```

Each property access performs I/O and returns the raw flag mask without raising
for reported instrument faults or querying other registers. They read and clear the selected register,
independently of enable masks. Reading them consumes events the automatic error
checks would otherwise see. `check_errors()` and `check_measurement_status()`
use these same queries to interpret faults and raise `InstrumentError`.

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

Normal checked writes already wait for command completion.
`wait_until_ready(timeout=10)` can wait for independently initiated operations,
using native VISA status polling where supported and a queued query otherwise.

`wait_for_settling()` queries the actual filter slope and time constant, then
waits the manual's approximate time to reach 99% of the final value:

| Slope | Time constants |
|---|---:|
| 6 dB/oct | 5 |
| 12 dB/oct | 7 |
| 18 dB/oct | 9 |
| 24 dB/oct | 10 |

These values come from the SR830 manual's "Intrinsic (Random) Noise Sources",
printed page 3-21 ([PDF page 49](https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf#page=49)).
Use `wait_for_settling(time_constants=20)` to override the multiplier. There is
no overall settling timeout; configuration queries retain normal VISA I/O
timeouts and error handling. This estimates low-pass settling rather than
measuring stability. Synchronous-filter transients, external reference locking,
and noise-estimate averaging are excluded.

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
methods. It interprets the inherited driver's command strings directly using its
own state, providing coherent X/Y/R/phase readings,
cascaded low-pass settling, offsets, display ratios, independent auxiliary inputs
and outputs, auto functions, saved setups, status registers, triggered and timed
acquisition, bounded circular buffers, all three trace encodings, and FAST counts.
Reset preserves the response interface and status registers, as on the instrument.

```python
import time

from sr830 import settings
from virtual_sr830 import VirtualSR830

with VirtualSR830(amplitude=0.005, phase=30.0) as instrument:
    instrument.connect()  # No resource name or manager is needed.
    instrument.time_constant = settings.TimeConstant.ms_100
    instrument.wait_for_settling()
    print(instrument.measure(settings.MeasurementParameter.R))

    instrument.sample_rate = settings.SampleRate.Hz_16
    instrument.start()
    time.sleep(0.25)
    instrument.pause()
    trace = instrument.get_ascii_buffer_data(1, 0, 4)
```

Constructor arguments describe external conditions, independently of instrument
configuration. `external_frequency` defaults to 1000.0 Hz, `external_locked` to
True, and `aux_inputs` to four zero-volt inputs in channel order. For example:

```python
instrument = VirtualSR830(
    amplitude=0.005,
    phase=30.0,
    external_frequency=137.0,
    external_locked=True,
    aux_inputs=(0.1, 0.2, 0.3, 0.4),
)
```

The reference source remains an ordinary instrument setting: select external
mode to use the supplied external frequency. Later changes use
`set_external_reference()` and `set_aux_input()`. Constructor inputs use the same
validation and survive resets and reconnects; auxiliary outputs are independent.

Virtual `connect()` defaults to GPIB. Select
`output_interface=settings.OutputInterface.RS232` explicitly to exercise serial
behavior; that choice controls framing validation and FAST availability.
Resource names and resource managers passed by shared hardware/application code
are accepted but ignored: the simulator never parses a VISA name, looks up a
manager, or opens a resource. The hardware driver's connection behavior is
unchanged.

`amplitude` is the nonnegative RMS input amplitude (default 0.001), and `phase` is
its input phase in degrees (default zero). Both are read/write properties that
can also be supplied to the constructor. Input X/Y targets are calculated as
`amplitude * cos(phase)` and `amplitude * sin(phase)`, with phase converted to
radians.
The instrument's `reference_phase_shift` rotates these components independently.
Changing either input property retains the filter state and settles through the
selected time constant and slope. Constructor inputs start at steady state.

The simulator uses monotonic elapsed time internally. Acquisition samples and
cascaded low-pass responses are calculated when the driver is accessed; no
background thread or caller-driven time stepping is needed. The hardware
`wait_until_ready()` and `wait_for_settling()` implementations are inherited.
FAST reads wait for samples and enforce their timeout budgets. Auto-phase,
auto-gain, auto-reserve, and auto-offset complete immediately. There is no public
clock, time-advance method, or signal callback. Tests patch internal time sources
to exercise the same calculations without waiting in real time.

Signal amplitudes are in V for voltage mode and A for current mode, before
offset and expansion. Changing input configuration does not rescale the input. `set_aux_input(channel, voltage)` and
`set_external_reference(frequency, locked=True)` supply external conditions;
`inject_status(register, mask)` supplies faults for application tests. Configuration
survives disconnect/reconnect, while I/O requires a connection.

This models an ideal demodulated signal, not the analog front end: notch filters,
AC coupling, synchronous rejection, input noise, calibration, overload distortion,
and reserve-dependent interference are not electrically simulated. Noise displays
read zero for the ideal input, and auto reserve selects low noise. Applications
can change amplitude and phase properties to model input changes.
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

Normal writes and successful queries check `*ESR?` and `ERRS?` directly,
independently of status enable masks. The queued check after a write also waits
for the preceding command to finish. `check_errors()` performs the same check
explicitly. Reported command, execution, queue, and device faults raise the
public `InstrumentError`, exported by both packages:

```python
from sr830 import InstrumentError

try:
    instrument.reference_frequency = 1000
except InstrumentError:
    logging.getLogger(__name__).exception("Instrument fault")
```

The exception message describes the detected faults; the traceback identifies
the operation. Faults may have been latched earlier. `measure()`,
`read_display()`, `measure_multiple()`, and buffer readers also check `LIAS?`
for overload and reference unlock; call `check_measurement_status()` explicitly
when needed. Configuration operations leave measurement status alone so callers
can correct an overload or unlock. Auxiliary voltage reads only check command
and device errors. FAST streaming defers checks until `pause()`, buffer reset,
instrument reset, or disabling FAST, after pending binary output is cleared;
streamed counts remain provisional until that check succeeds.

These checks read and clear event registers, including ordinary events such as
power-on, triggers, and time-constant changes. Those events and message-available
status are not errors. Explicit `get_status_byte()` and `serial_poll()` remain
available for raw diagnostics without automatic checks. If preserving event
history matters, account for the automatic register reads. See the
[SR830 programming manual](https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf).

A query timeout can indicate a rejected command, a slow response, or a transport
problem. On native GPIB the driver attempts VISA device clear and error checks
with a one-second diagnostic I/O timeout. A confirmed fault raises
`InstrumentError` chained from the original VISA timeout; an inconclusive check
or no reported fault preserves the original timeout. Serial and ambiguous
adapter transports cannot guarantee that a delayed response has been discarded,
so they preserve the timeout without sending diagnostic queries. Reconnect after
an unrecovered timeout or incomplete binary response before further I/O. The
normal VISA timeout still controls ordinary operations. No automatic command
retry is performed. Recovery and adapter behavior require hardware validation.

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

Use ty for type checking and Ruff for linting and formatting:

```sh
uv run --locked ty check
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Both tools are configured in `pyproject.toml` and infer the minimum supported
Python version from `requires-python`. ty checks source, examples, and tests.
Ruff checks common errors and import ordering, and formats Python code and
Python examples in Markdown. To apply formatting or automatic lint fixes:

```sh
uv run --locked ruff check --fix .
uv run --locked ruff format .
```

Build distributions with `uv build`.

Use `uv add <package>` for runtime dependencies, `uv add --dev <package>` for
development tools, and `uv lock --upgrade-package <package>` for a targeted
lockfile update. `uv sync --locked` verifies that the lockfile matches
`pyproject.toml` before installing it.
