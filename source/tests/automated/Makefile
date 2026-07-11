# Makefile for the dojo automated-test scaffold
# Usage:
#   make sync    -> create/update the uv-managed virtual environment
#   make test    -> run the full test suite, writes HTML + JUnit XML to tests/output/
#   make swtest  -> run only tests that don't need real hardware attached (-m "not hardware")
#   make smoke   -> run only smokeTest-marked tests
#   make fixture -> run only the isTestFixtureOk pretest
#   make report  -> alias for 'make test'
#   make serial  -> open an interactive console on the target's UART (Ctrl+] to exit)
#   make ssh     -> SSH to the target and live-tail a systemd service's journal (Ctrl+C to exit)
#   make clean   -> remove test output artifacts

.PHONY: sync test swtest smoke fixture report serial ssh clean

HAS_UV := $(shell if command -v uv >/dev/null 2>&1; then echo 1; else echo 0; fi)
PYTEST_RUN := $(if $(filter 1,$(HAS_UV)),uv run --active pytest,python -m pytest)
PYTHON_RUN := $(if $(filter 1,$(HAS_UV)),uv run --active python,python3)

# DOJO_SSH_PASSWORD is read by coms.sshCreate() as a fallback when no password
# is passed explicitly (see readme.md "SSH credentials"). Deliberately left
# unset here - this scaffold doesn't ship any real device's default password.
# Set it before running ssh-dependent targets, e.g.:
#   DOJO_SSH_PASSWORD=<pw> make test

# tests/output, a sibling of tests/automated
OUTPUT_DIR := $(abspath ../output)
REPORT_OPTS := --html=$(OUTPUT_DIR)/report.html --self-contained-html --junitxml=$(OUTPUT_DIR)/junit.xml

sync:
	uv sync --all-groups

test:
	$(PYTEST_RUN) -vv $(REPORT_OPTS)

swtest:
	$(PYTEST_RUN) -vv -m "not hardware" $(REPORT_OPTS)

smoke:
	$(PYTEST_RUN) -vv -m smokeTest $(REPORT_OPTS)

fixture:
	$(PYTEST_RUN) -vv -m isTestFixtureOk $(REPORT_OPTS)

report: test

serial:
	$(PYTHON_RUN) serial_console.py

ssh:
	$(PYTHON_RUN) ssh_console.py

clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .pytest_cache
