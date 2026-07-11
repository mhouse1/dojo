# Change log
* maintain the same syntax for each version

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
