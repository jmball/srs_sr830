# Repository guidance

## Project and layout

This repository provides Python control of a Stanford Research Systems SR830
lock-in amplifier over PyVISA, plus a virtual instrument for development.

- `src/sr830/sr830.py`: hardware driver, VISA connection lifecycle, instrument
  settings, measurements, buffer transfers, and status registers.
- `src/virtual_sr830/virtual_sr830.py`: in-memory implementation of the same
  public interface, with dummy settings and measurement values. It is not a
  complete simulation of the instrument or a VISA resource.
- Each package's `__init__.py` exports its implementation and obtains a version
  through `importlib.metadata` for the `srs_sr830` distribution, falling back to
  `0.0.0`.
- `src/sr830/test_sr830.py`: existing hardware integration tests.
- `examples/logging.py`: logging and serial connection example. Running it
  opens a real resource.
- `src/sr830/_connection.py`: shared interface inference and framing validation.
- `tests/test_connection.py`: hardware-free lifecycle and annotation checks,
  run with `python -m unittest discover -s tests`.
- `pyproject.toml`: package metadata, package discovery, runtime dependencies
  (`pyvisa` and `pyvisa-py`), and the setuptools build backend. Keep installation
  configuration here; there is no `setup.cfg` or `setup.py`.

The distribution is named `srs_sr830`; imports are `sr830` and `virtual_sr830`.
Both expose a lowercase `sr830` class, for example `sr830.sr830()`.

## Development conventions

- Keep changes focused and preserve existing public names, signatures, setting
  indices, units, return types, and validation behavior unless the task requires
  an API change.
- When changing a shared setting or method, inspect both implementations and
  update the virtual instrument where appropriate. Keep its dummy defaults and
  validation consistent with the intended hardware interface.
- Follow the existing four-space indentation, snake_case methods and properties,
  and NumPy-style docstrings describing parameters, ranges, and units.
- Hardware getters query `self.instr`; setters validate values before writing
  instrument commands. Preserve command spelling, channel numbering, and
  interface-specific binary transfer behavior.
- The SR830 programming manual is linked in both implementation module
  docstrings. Consult it when changing protocol behavior.
- Python >=3.10 is required. Preserve this minimum unless the task changes
  compatibility.
- No CI, formatter, or linter is configured. Both packages ship `py.typed`.
  Driver annotations can be checked with `mypy --strict --follow-imports=silent
  src/sr830/sr830.py src/sr830/_connection.py
  src/virtual_sr830/virtual_sr830.py` (install mypy separately).

## Setup and validation

Use an isolated environment when dependencies are needed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

A syntax check that does not open hardware is:

```sh
python3 -m compileall -q src examples
```

For driver behavior changes, prefer focused checks using a fake VISA resource
or the virtual instrument. Verify relevant commands, conversions, valid range
boundaries, and invalid values. Report which checks ran and whether hardware
behavior remains unverified.

Do not run blanket `pytest` collection as a default check. The existing test
module imports legacy `visa`, requires `numpy` and `pytest` (not declared as
runtime dependencies), and calls `argparse.parse_args()` at import time, which
can conflict with pytest arguments. It uses one global instrument and depends
on connection/reset/disconnection tests and instrument state. Its property
helpers assign local values rather than invoking the actual property setters,
so they do not establish setter correctness. Inspect and address these issues
before relying on this suite.

Real hardware runs require a user-provided VISA resource and appropriate
authorization to change its settings. `connect()` never resets the instrument;
reset is an explicit caller operation. It enables status registers and selects
the response interface (`0` RS232, `1` GPIB), inferred for ASRL/GPIB and explicit
for ambiguous adapters. Local mode and lockout are explicit caller settings via
`local_mode`; `connect()` rejects the removed `local_lockout` option and sends
no `LOCL` command. Connection options are keyword-only,
conflicting framing is rejected, and connecting twice raises. Disconnect clears
`instr`, is idempotent, and closes only the resource; managers remain open
because PyVISA shares them. Disconnect after hardware work; the hardware
driver's context manager calls `disconnect()` on exit.

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
