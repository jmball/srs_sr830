# Running the tests

```sh
uv sync --locked
uv run --locked pytest
```

The default run opens no hardware. Unit tests use fake VISA resources; integration
tests connect a fresh `VirtualSR830` for each test, including registers and real
simulated acquisition. No hardware is opened without an explicit resource.

## Layout

| Location | Purpose |
| --- | --- |
| `unit/test_connection.py` | Initialization, cleanup, reconnection, framing, and binary transfers |
| `unit/test_settings.py` | Parametrized integer/enum codes, commands, and getter types |
| `unit/test_enums.py` | Named selectors, enum validation, register masks, and buffer modes |
| `unit/test_protocol_regressions.py` | Strict integer fields, transfer failures, explicit resume, FAST decoding, and timeout recovery |
| `unit/test_simulation.py` | Deterministic filters, signals, setups, registers, acquisition, and streaming |
| `unit/test_logging.py` | Library logging policy, warnings, and error decoding |
| `unit/test_instrument_fixtures.py` | Backend selection, option forwarding, failures, and restoration with fake VISA |
| `integration/test_settings.py` | Setting, display, expansion, and auxiliary-output round trips |
| `integration/test_measurements.py` | Identification and finite public measurement results |
| `integration/test_buffers.py` | Acquisition/readout through the same hardware or virtual interface |
| `integration/test_status.py` | Register masks and status reads on both backends |
| `conftest.py` | CLI options and integration fixtures |
| `unit/conftest.py` | Unit-test mocks |
| `support.py`, `cases.py` | Shared helpers and test data |

Tests use pytest functions, fixtures, parametrization, and plain assertions.
`unittest.mock` is retained for fake VISA calls; there are no unittest test classes.
Each test owns its connection and restores the properties it changes, so tests
can run individually without depending on earlier tests. No test resets the
instrument to obtain its initial state.

## Real hardware

Provide a VISA resource to run integration tests on an SR830. For native serial
access through the Python backend, select the serial extra:

```sh
uv sync --locked --extra serial
```

```sh
# Serial settings must match the front panel. The SR830 always requires 8 data bits.
uv run --locked --extra serial pytest tests/integration --resource-name "ASRL2::INSTR" \
    --visa-backend=@py --baud-rate 9600 --data-bits 8 --parity none --stop-bits 1

# Native GPIB response routing is inferred.
uv run --locked pytest tests/integration --resource-name "GPIB0::8::INSTR"

# Ambiguous Ethernet-to-GPIB adapter: explicitly choose the downstream interface.
uv run --locked pytest tests/integration \
    --resource-name "TCPIP0::192.0.2.10::1234::SOCKET" --output-interface 1
```

Keep `--extra serial` on `uv run` commands that need the serial extra; uv
synchronizes the selected extras for each run.

Use `--visa-backend=@py`, including the equals sign: pytest interprets a separate
`@py` argument as an argument-file reference. An explicit resource is never
silently replaced with a virtual instrument if connection or initialization fails.
The fixture checks the model identification before yielding the instrument to a
test, closes the resource on exit, and closes the resource manager it creates.
Unit tests keep using fake VISA resources even during a hardware run.

| Option | Meaning | Default |
| --- | --- | --- |
| `--resource-name` | VISA resource or alias | VirtualSR830 |
| `--visa-backend` | PyVISA backend or library path | PyVISA default |
| `--output-interface` | Instrument-side RS232 (0) or GPIB (1) | Infer for native ASRL/GPIB |
| `--visa-timeout` | VISA I/O timeout in milliseconds | 5000 |
| `--baud-rate` | Serial baud rate | VISA default |
| `--data-bits` | Serial data bits: 8 | Driver 8 |
| `--parity` | none, odd, even, mark, or space | VISA default |
| `--stop-bits` | 1, 1.5, or 2 | VISA default |
| `--write-termination` | LF, CR, or CRLF | Driver LF |
| `--acquisition-timeout` | Maximum buffer-acquisition wait in seconds | 10 |

Serial options configure native VISA serial resources; configure the serial side
of an Ethernet adapter using the adapter's own interface. Tests do not set an
instrument's GPIB address or serial baud rate remotely.

Hardware tests exercise real I/O and temporarily change input configuration,
sensitivity, filters, reference and auxiliary outputs, displays, and local mode.
Fixtures attempt to restore changed properties even after failed assertions;
cleanup failures are reported. Connection initialization enables status registers,
status queries clear latched events, and disconnect returns the front panel to
local mode. Buffer tests stop acquisition and erase the existing trace buffers;
previous buffer contents and scan activity cannot be restored.

The virtual driver models demodulated signals, settling, acquisition, registers,
and saved setups. Unit simulation tests inject a fixed clock and advance time
without sleeping; integration fixtures acquire actual simulated buffer points.
See the [simulation guide](../README.md#simulation) for controls and physical scope.
Physical signal accuracy and transport compatibility require a hardware run.

## Selection and coverage

```sh
uv run --locked pytest -m unit
uv run --locked pytest -m integration
uv run --locked pytest -m hardware --resource-name "GPIB0::8::INSTR"
uv run --locked pytest --cov --cov-report=term-missing
```

Without a resource, `hardware` selects no tests. With a resource, all integration
tests are marked `hardware`. Collection and `--help`
never connect an instrument. Avoid parallel execution against a single physical
instrument; changing its settings from multiple tests concurrently is unsupported.
