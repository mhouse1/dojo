# Change log
* maintain the same syntax for each version

## 0.0.2 power control (docs/research/001-np-05b-network-controlled-power-outlet.md)
* added `power_control.py`: control of a Synaccess NP-05B network-switched PDU over either
  transport - local IP ethernet via the `cmd.cgi` HTTP API (stdlib only) or the USB serial console
  (pyserial, already pinned) - with identical methods on both, so a test neither knows nor cares
  which one it got. Named for the function rather than the device class because "PDU" collides with
  Protocol Data Unit in a directory otherwise full of transport helpers.
* added `test_power_control.py`: hardware-independent tests covering the command strings and URLs
  each transport builds, `$A5` state parsing (including the reversed bit order, where an off-by-one
  reads as "the DUT is powered" when it isn't), the `pshow` table parse and its pager handling, the
  rejection paths that keep a refused command from looking like an accepted one, and
  `power_cycle()`'s guarantee that power is restored when the dwell is interrupted. No marker, so
  they run under `make swtest` and in CI where no PDU exists.
* `pre_test.py` now imports `power_control` as part of its fixture-health check, so a syntax error
  or bad import in it fails one obvious blocker rather than surfacing later
* the serial transport is still unvalidated against real hardware: `SERIAL_ERROR_RE`, `PAGER_RE`
  and `PduSerial._login()` come from the vendor manual and are collected at the top of the module
  so confirming them on first use is an edit in one place

## 0.0.1 initial scaffold (docs/adr/001-adopt-mos-docker-hil-test-suite-architecture.md)
* seeded from mos-docker/tests/automated (Anaconda OS's HIL suite, version 0.0.13 at the time of
  extraction) per dojo ADR 001: the architecture - config/state split, conftest.py's blocker
  mechanism and step-narration fixture, coms.py's SSH/serial primitives, the static-report
  fallback, and the Makefile/Jenkinsfile command surface - is carried over as working code, since
  SSH and serial are near-universal for embedded HIL testing. Product-specific values (private-net
  defaults, RAUC OTA handling, cutiepi-shell references) were generalized or dropped; see the ADR's
  mapping table for the full list.
* renamed `MOS_SSH_PASSWORD` to `DOJO_SSH_PASSWORD`, shipped unset (no baked-in default password)
* deduplicated the report title (previously hardcoded separately in `conftest.py` and
  `reporting.py`) into one `test_parameters.report_title` constant
* dropped `sys_update_file`/`expected_version` CLI options and fixtures, the `pytest_html_results_table_header`/`_row` hooks (Version Before/After columns), and the `systemUpdate` marker -
  all existed only to support the RAUC OTA test this scaffold doesn't carry over
* dropped `main.py` (pytest-feature demo) and `test_cutiepi_shell_build_contract.py`/
  `test_cutiepi_shell_runtime_contract.py` (Yocto-recipe- and cutiepi-shell-specific, no generic
  analog); added `test_example_ssh.py` as the working example of the "one file per feature"
  pattern instead
* `usb_test.py`'s `known_hardware` ships empty with a documented format instead of real serial
  numbers; `serial_monitor()` takes an `expected_text` parameter instead of a hardcoded
  `'hello world'` scan target
