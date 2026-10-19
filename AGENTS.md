# Repository guidance

## Project and layout

This repository provides Python control of a Stanford Research Systems SR830
lock-in amplifier over PyVISA, plus a virtual instrument for development.

- `src/sr830/sr830.py`: hardware driver, VISA connection lifecycle, instrument
  settings, measurements, buffer transfers, and status registers.
- `src/virtual_sr830/virtual_sr830.py`: simulator inheriting the hardware public
  interface, with connection/I/O adapters and simulation controls.
- `src/virtual_sr830/_simulation.py`: stateful demodulated-signal model, filters,
  acquisition, setups, protocol responses, and registers; opens no VISA resource.
- Each package's `__init__.py` exports its implementation and obtains a version
  through `importlib.metadata` for the `srs_sr830` distribution, falling back to
  `0.0.0`.
- `examples/configure_and_measure.py`: hardware-only configuration and measurement
  guide; requires --resource-name and changes instrument settings.
- `examples/configure_and_measure_virtual.py`: standalone virtual configuration
  and measurement guide; opens no hardware. Keep configuration inline in each
  example rather than sharing a helper between them.
- `examples/connect_with_logging.py`: logging and serial connection example. Running it
  opens a real resource.
- `src/sr830/_connection.py`: shared interface inference and framing validation.
- `src/sr830/exceptions.py`: InstrumentError and shared fault decoding.
- `src/sr830/settings.py`: public setting/selector enums, documented units and
  meanings, and private protocol mappings/validation shared by both drivers.
  Enum values are instrument command codes, not physical values. There is no
  `_Settings` base class or legacy value/description tables.
- `tests/unit/`: native pytest unit tests for connections, I/O, enums, logging,
  and test-fixture behavior. Tests are grouped by validation, connections, buffers,
  FAST transfers, waiting, and simulation. They never open hardware.
- `tests/integration/`: public-interface setting, measurement, buffer, and status
  tests. These use VirtualSR830 unless --resource-name selects real hardware.
- `tests/conftest.py`: CLI options, backend selection, markers, and integration
  fixtures. `tests/unit/conftest.py` contains fresh unit-test mocks.
- `tests/support.py`: shared connection options, cleanup/restoration helpers, and
  ManualClock for deterministic completion/settling tests.
- `tests/cases.py`: shared setting/command cases; do not import another test module.
- `tests/README.md`: test commands, hardware options, and virtual limitations.
- `pyproject.toml`: package metadata, package discovery, runtime dependencies
  (`pyvisa` and `pyvisa-py`), the serial extra, the dev dependency group, pytest
  and coverage settings, and the setuptools build backend. Keep installation
  configuration here; there is no `setup.cfg` or `setup.py`.
- `uv.lock`: committed universal dependency lockfile. Update it with dependency
  changes; do not pin the supported Python range to a single local interpreter.

The distribution is named `srs_sr830`; imports are `sr830` and `virtual_sr830`.
The hardware class is `sr830.SR830`; the virtual class is
`virtual_sr830.VirtualSR830`. Export these explicitly from their packages.

## Development conventions

- Keep changes focused and preserve existing public names, signatures, setting
  indices, units, return types, and validation behavior unless the task requires
  an API change.
- When changing a shared setting or method, inspect both implementations and
  update the virtual instrument where appropriate. Keep its documented instrument defaults and
  validation consistent with the intended hardware interface.
- Define enum codes only in `src/sr830/settings.py`; both packages export the
  same enums. Integer calls and getter return types remain supported. Enum
  inputs must match the setting and, for display/ratio enums, the channel.
  Register bit-position enums and IntFlag masks must match their register and
  must not be interchanged. Explicitly serialize command codes as integers,
  including SNAP lists, for Python 3.10 compatibility. Values with units use
  <unit>_<value> (ms_100, dB_12, Hz_512); multipliers use x<value> (x1u, x10).
  Describe units and member meanings in enum docstrings, not parallel tables.
  Sensitivity multipliers select RMS full-scale amplitudes in V for voltage
  inputs or microamps for current inputs; they do not represent amplifier gain.
  OutputExpansion.x1 has code 0 and represents no expansion (unity gain).
- Follow the existing four-space indentation, snake_case methods and properties,
  and NumPy-style docstrings describing parameters, ranges, and units.
- The hardware VISA resource is private (`self._instr`). Driver I/O uses
  checked `_write()`, `_query()`, `_query_ascii_values()`, and
  `_read_buffer_bytes()` helpers, backed by raw transport helpers. Normal I/O
  checks command/device faults through *ESR?/ERRS?; measurements additionally
  check LIAS?. Explicit status reads bypass automatic checks. FAST checks wait
  until pending stream bytes have been cleared. Inline guards raise RuntimeError
  when disconnected, using a shared message constant. Direct resource access is reserved for
  connection lifecycle and framing configuration. Setters validate values before
  writing commands. Preserve command spelling, channel numbering, and
  interface-specific binary transfer behavior.
- The SR830 programming manual is linked in both implementation module
  docstrings. Consult it when changing protocol behavior.
- Python >=3.10 is required. Preserve this minimum unless the task changes
  compatibility.
- Keep logging configuration in applications. The driver uses a module logger
  with NullHandler and DEBUG lifecycle diagnostics; it must not configure the
  root logger, capture warnings globally, or print. Instrument faults raise
  InstrumentError silently; check_errors() replaces the removed errors property.
  Serial-transfer warnings use `stacklevel=2`.
- No CI, formatter, or linter is configured. Both packages ship `py.typed`.
  Driver annotations can be checked with `uv run --locked mypy --strict --follow-imports=silent
  src/sr830/settings.py src/sr830/sr830.py src/sr830/_connection.py src/sr830/exceptions.py
  src/virtual_sr830/virtual_sr830.py src/virtual_sr830/_simulation.py` (included in the dev group).

## Setup and validation

Use uv to manage the project environment and locked dependencies:

```sh
uv sync --locked
```

A syntax check that does not open hardware is:

```sh
uv run --locked python -m compileall -q src tests examples
```

For driver behavior changes, prefer focused checks using a fake VISA resource
or the virtual instrument. Verify relevant commands, conversions, valid range
boundaries, and invalid values. Report which checks ran and whether hardware
behavior remains unverified.

Use `uv run --locked pytest` for normal validation; tests are discovered only under
`tests/`. `uv run --locked pytest -m unit` selects isolated tests, and
`uv run --locked pytest --cov --cov-report=term-missing` reports line/branch coverage.
Development dependencies are declared in the `dev` dependency group in pyproject.toml. Keep tests
as pytest functions using fixtures, parametrization, and plain assertions.
There is no legacy test module in src and no import-time argument parsing.
Use query_replies to map stable VISA query responses by command; reserve ordered
side_effect lists for intentionally changing replies or query-order assertions.
Keep validation in shared helpers instead of repeating checks inside register methods.
Favor representative, independent wire contracts and behavioral tests over exhaustive
setting/member/type products. Test shared validation once thoroughly and check its
use at other entry points; do not duplicate inherited validation on the simulator.
Expected wire codes should be literal, manual-backed values rather than derived
from the enum under test. Use mypy for annotations; coverage is diagnostic, not a target.

Use `uv add --dev` for development tools, `uv add` for runtime dependencies,
and `uv lock --upgrade-package` for targeted updates. Commit pyproject.toml and
uv.lock together. Use `uv build` for distributions. The default dev group includes
pytest, pytest-cov, and mypy. For serial hardware, keep `--extra serial` on both
`uv sync` and `uv run` commands so synchronization retains pyserial.

Integration fixtures create fresh connections and restore changed properties even
when tests fail. Supplying --resource-name selects real hardware; a connection
failure must fail rather than silently fall back to virtual. Optional arguments
include --visa-backend, --output-interface, --visa-timeout (ms), serial framing,
and --acquisition-timeout (seconds). Spell the backend as --visa-backend=@py;
pytest treats a standalone @py as an argument-file reference. Buffer tests
pause and clear acquisition buffers on both backends. Register tests also run
on both backends. Verify fixture selection/cleanup with fake resources; do not
claim virtual runs validate hardware.

Real hardware runs require a user-provided VISA resource and appropriate
authorization to change its settings. `connect()` never resets the instrument;
reset is an explicit caller operation. It enables status registers and selects
the response interface (`0` RS232, `1` GPIB), inferred for ASRL/GPIB and explicit
for ambiguous adapters. Local mode and lockout are explicit caller settings via
`local_mode`; `connect()` sends no `LOCL` command. Connection options are keyword-only,
conflicting framing is rejected, and connecting twice raises. Disconnect clears
`_instr`, is idempotent, and closes only the resource; managers remain open
because PyVISA shares them. The VISA resource retains its manager; the driver
does not store a separate manager reference. Disconnect after hardware work;
the hardware driver's context manager calls `disconnect()` on exit.

## Acquisition and simulation conventions

- Integer protocol fields reject floats (including 1.0) and bools before I/O.
  Native serial connections require 8 data bits for all commands.
- Trace readers validate capacity and acquired length, reject short responses,
  and pause loop scans. They leave loop scans paused unless resume=True explicitly
  requests start() after success. Failures leave the scan paused.
- FAST transfers are GPIB-only, decoded as signed little-endian X/Y count pairs.
  Guard text queries while streaming; stop/discard pending FAST output with VISA
  clear before returning to text I/O. Preserve framing and timeout on failures.
- Query-timeout recovery attempts device clear and diagnostics only on native
  GPIB; preserve the original VISA timeout if no fault is confirmed. Unrecovered
  timeouts and short binary responses require reconnecting before further I/O.
- Completion/settling helpers have finite timeout budgets. Settling estimates a
  multiple of the low-pass time constant, not physical measurement stability.
- Simulation tests use an injected clock and advance_time(), not real sleeps.
  Keep physical units, phase, display offsets/ratios, buffer cadence, register
  latching/clear-on-read, and setup copies consistent. Expand changes ordinary
  display resolution rather than its amplitude; FAST counts and ratios include it.
  The model accepts demodulated inputs, not raw electrical waveforms; document
  analog scope honestly instead of claiming calibrated hardware equivalence.

## Development VM environment

This guest is provisioned by the `dev-vm` repository and intentionally uses a
host-managed network sandbox.

Private and local IPv4 destinations are blocked by default. If networked
hardware appears unreachable, do not assume that the device or its service is
down until this policy has been considered. Ask the user to run the following
on the host from the `dev-vm` repository:

```sh
./manage-network-access.sh add <IPv4-address>
```

For a persistent exception, the user can add the exact address to
`SANDBOX_ALLOWED_IPV4_DESTINATIONS` in the `dev-vm` repository's
`vm-config.sh`. The guest cannot change the host policy and should not attempt
to bypass it.

## Private project clones

Repositories beneath `/workspaces/projects` are private guest clones managed
from the host by the `dev-vm` repository. They are not mounted host working
trees. The host cannot see uncommitted guest files, and the guest does not have
the host's upstream Git credentials.

When work needs to be returned to the host, ensure the relevant repositories
are clean and the intended changes are committed. For submodules, commit inside
the deepest changed submodule first, then commit each updated gitlink while
working outward through its parents. Tell the user to run this from the
`dev-vm` repository on the host:

```sh
./pull-project-changes.sh <host-project-path>
```

If the user says that host changes have been pushed into the VM, or asks to
integrate `host/*` references, invoke `$integrate-host-changes`. Do not guess at
the pending refs or discard guest work.

The project lifecycle scripts are host-side controls. Do not try to run them
inside the guest or bypass the private-clone boundary; ask the user to run the
appropriate command from the host's `dev-vm` repository.

## Guest account boundary

Coding agents run as the unprivileged `agent` account. It can access projects,
USB development devices through `dialout`, and its own rootless Docker daemon,
but it does not have sudo or access to the rootful Docker socket. Do not try to
switch to the administrative `dev` account or bypass this boundary. When a
task genuinely requires guest administration, explain the required command
and ask the user to perform it through the host-managed update workflow or an
administrative SSH session.
