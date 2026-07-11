# Overview
Scaffold pytest suite for embedded hardware-in-the-loop (HIL) testing - a starting point, not a
runnable example. It's inert until you fill in `coms.py`'s target-specific bits (if any),
`test_parameters.py`'s defaults, and real `test_*.py` feature files. See
`docs/adr/001-adopt-mos-docker-hil-test-suite-architecture.md` (dojo repo) for why this scaffold is
shaped the way it is.

# Setup
This test suite is managed with [uv](https://github.com/astral-sh/uv). Install uv first:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, from this directory, sync the environment (creates `.venv` and installs everything
pinned in `pyproject.toml` / `uv.lock`, including dev-only tools like pytest):
```
uv sync --all-groups
```

uv reads `.python-version` and downloads a matching interpreter automatically if one
isn't already installed, so a separate pyenv setup is not required.

# Running tests
```
uv run pytest -vv
```

Or use the Makefile shortcuts:
```
make sync      # create/update the environment
make test      # run the full suite, writes HTML + JUnit XML to tests/output/
make swtest    # run only tests that don't need real hardware attached (-m "not hardware")
make smoke     # run only smokeTest-marked tests
make fixture   # run only the isTestFixtureOk pretest
make report    # alias for 'make test'
make serial    # open an interactive console on the target's UART (Ctrl+] to exit)
make ssh       # SSH to the target and live-tail a systemd service's journal (Ctrl+C to exit)
make clean     # remove tests/output and .pytest_cache
```

`tests/output/` is a sibling of this directory (`tests/automated/`), not nested inside it - keeps
generated reports out of the source tree and easy to exclude from version control with a single
`.gitignore` entry at the repo root. It's git-ignored. Both `report.html` (human-readable) and
`junit.xml` (for CI systems like Jenkins) are written there.

## Adding a new test
1. **Pick (or create) a file by feature area, not by chance.** Each `test_*.py` file should cover
   one feature or decision record - see `test_example_ssh.py` for the shape to copy, then delete
   it once real feature tests exist. Add to the matching file; only start a new one when the test
   doesn't fit any existing feature area.
2. **Mark hardware-dependent tests.** If *every* test in a file needs the real target, set
   `pytestmark = pytest.mark.hardware` once at module level (see `test_example_ssh.py`) rather than
   repeating `@pytest.mark.hardware` on each test - that also means a new test added later to that
   file can't forget it. Only decorate individual tests when a file has a genuine mix of hardware
   and non-hardware tests.
3. **Use the `ssh_client` fixture for anything that needs one SSH connection.** It creates the
   connection, hands it to the test, and always closes it in teardown - including on test
   failure - so you don't need your own `try`/`finally: coms.sshFree(...)`. Only manage a
   connection manually (`coms.sshCreate()`/`coms.sshFree()`) if your test genuinely needs more than
   one connection in sequence (e.g. a reboot in the middle).
4. **Introducing a new marker?** Register it in `pyproject.toml`'s `[tool.pytest.ini_options]`
   `markers` list - `--strict-markers` is enabled, so an unregistered marker fails loudly instead
   of silently collecting nothing.
5. **Bump `test_parameters.automated_test_version` and add a `CHANGELOG.md` entry** describing
   what changed and why. `pre_test.py::test_changelog_version_matches` checks these two stay in
   sync and fails the run if you update one without the other.

## Serial port auto-detection
By default nothing scans serial ports. Pass `--scan-serial-ports` to have `conftest.py` scan all
serial ports at session start and auto-select `test_parameters.my_serial_port` based on known
hardware serial numbers (see `usb_test.assign_known_hardware`) - fill in `usb_test.py`'s
`known_hardware` dict with your board's serial numbers first. It's opt-in because the scan is slow
and noisy and most test runs don't need it.

## SSH credentials
`coms.sshCreate()` accepts a `password` argument, but if omitted it falls back to the
`DOJO_SSH_PASSWORD` environment variable so credentials don't need to be hardcoded in test code or
CI job configuration. It ships unset - set it before running anything that opens an SSH connection:
```
DOJO_SSH_PASSWORD=<pw> make test
```

# Adding a dependency
```
uv add <package>          # runtime dependency
uv add --dev <package>    # test-only dependency
```
This updates `pyproject.toml` and `uv.lock` together - commit both.
