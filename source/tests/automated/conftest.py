'''
This test is required by pytest, it defines some pytest settings, start, end and configuration
'''
import html
import pytest, warnings
import coms, reporting, session_state, test_parameters

REPORT_SUMMARIES = {}

# test_parameters.py and usb_test.py are helper modules, not test suites, but their names
# happen to match pytest's default test-file glob (test_*.py / *_test.py). Excluding them
# here keeps them from being silently auto-collected the day either one grows a function
# named test_something. session_state.py doesn't match that glob (nothing to exclude).
collect_ignore = ["test_parameters.py", "usb_test.py"]

def pytest_sessionstart(session):
    ''' This function runs at the start of pytest session'''
    print(f'========== Pytest starting ===========')

    # take the command line args and update the test_parameters
    test_parameters.my_serial_port = session.config.getoption("myserialport")

    session_state.test_marker_used = session.config.getoption('-m')

    # scanning every serial port is slow and noisy, so it's opt-in via --scan-serial-ports
    # rather than running on every single session regardless of which tests are selected
    if session.config.getoption("scan_serial_ports"):
        try:
            import usb_test
            known_hardware = usb_test.assign_known_hardware()
            # placeholder key - matches usb_test.py's known_hardware format;
            # replace with your own board's key once known_hardware is filled in
            if 'my-board-console' in known_hardware.keys():
                test_parameters.my_serial_port = known_hardware['my-board-console']
        except Exception as e:
            warnings.warn('unable to auto assign serial port using serialnumbers')
            warnings.warn(str(e))

def pytest_collection_modifyitems(config, items):
    '''
    This runs before any tests, it adjusts markers based on commandline options,
    this function runs after pytest_sessionstart
    '''

    if config.getoption('--ignore_test_blockers'):
        session_state.ignore_blockers = True


def pytest_addoption(parser):
    '''
    Define custom pytest commandline parameters
    '''
    print('='*30, f'Running Automated Test Version: {test_parameters.automated_test_version}')

    parser.addoption(
        "--myserialport", action="store", default=test_parameters.my_serial_port, help= "serial port name to use"
    )

    parser.addoption(
        "--ignore_test_blockers", action="store_true", default=False, help= "allows ignoring test blockers"
    )

    parser.addoption(
        "--scan-serial-ports", action="store_true", default=False,
        help="scan all serial ports at session start to auto-detect known hardware (slow, noisy; opt-in)"
    )

    parser.addoption(
        "--target-host", action="store", default=test_parameters.target_host,
        help="address of the target under test"
    )

    parser.addoption(
        "--target-user", action="store", default=test_parameters.target_user,
        help="SSH username for the target under test"
    )


############## test fixtures
# All "CLI option mirror" fixtures below are session-scoped: each reads one
# pytest.addoption default exactly once and returns it - none of them have
# any reason to be recomputed per-module.
@pytest.fixture(scope="session")
def my_serial_port(pytestconfig):
    test_parameters.my_serial_port = pytestconfig.getoption("myserialport")
    return test_parameters.my_serial_port

@pytest.fixture(scope="session")
def target_host(pytestconfig):
    test_parameters.target_host = pytestconfig.getoption("target_host")
    return test_parameters.target_host

@pytest.fixture(scope="session")
def target_user(pytestconfig):
    test_parameters.target_user = pytestconfig.getoption("target_user")
    return test_parameters.target_user

@pytest.fixture
def ssh_client(target_host, target_user):
    '''
    Owns one SSH connection's full lifecycle: creates it, hands it to the test,
    and always closes it in teardown - including when the test fails - so
    individual tests don't need their own try/finally: sshFree() boilerplate,
    and there's no separate connection count to keep in sync by hand.

    Function-scoped (a fresh connection per test). If a test needs more than
    one connection in sequence (e.g. a reboot in the middle), manage the
    connection manually with coms.sshCreate()/sshFree() instead - that doesn't
    fit a single setup/teardown pair.
    '''
    ssh = coms.sshCreate(target_host, 22, target_user)
    yield ssh
    coms.sshFree(ssh)

@pytest.fixture
def step(record_property, request):
    '''
    One call, two audiences: print() keeps console/-s behavior and feeds
    --junitxml's <system-out> once junit_logging is set; record_property("step", ...)
    feeds pytest_html_results_table_html below. Order across multiple calls in
    the same test is preserved (record_property allows repeated names - a
    dict() over report.user_properties would silently keep only the last one,
    which is why that hook uses a list comprehension instead).
    '''
    def _step(message):
        print(f"step: {message}")
        record_property("step", message)
        request.node._store.setdefault("hil_steps", []).append(message)
    return _step

##################################

@pytest.fixture(autouse=True)
def setup_test():
    '''
    This runs at the beginning of any tests
    '''

    # exit early if a test blocker failed
    if session_state.blocker_failed:
        pytest.exit("A blocker failed, exiting early")

def pytest_runtest_makereport(item, call):
    '''
    If a test marked isTestFixtureOk fails (setup or call), flag it as a blocker so the
    autouse setup_test fixture above can abort the rest of the session instead of burning
    time on tests that would fail anyway. Skipped when --ignore_test_blockers is passed.
    '''
    if call.when in ("setup", "call") and call.excinfo is not None:
        if item.get_closest_marker("isTestFixtureOk") and not session_state.ignore_blockers:
            session_state.blocker_failed = True


def pytest_runtest_logreport(report):
    '''Record the final call-level report for the fallback HTML summary.'''
    if report.when == "call":
        steps = [value for name, value in getattr(report, 'user_properties', []) if name == 'step']
        outcome = 'passed' if report.passed else 'failed' if report.failed else 'skipped' if report.skipped else 'xfailed' if report.xfailed else 'xpassed' if report.xpassed else 'error'
        details = ''
        if report.failed:
            details = 'Test failed'
        REPORT_SUMMARIES[report.nodeid] = {
            'nodeid': report.nodeid,
            'outcome': outcome,
            'duration': getattr(report, 'duration', 0.0),
            'steps': steps,
            'details': details,
        }

def pytest_sessionfinish(session):
    '''Runs once at the end of a pytest session'''
    print('\n pytest session finished ... cleaning up')

    pytest_status = 'PASS' if session.testsfailed == 0 else 'FAILED'
    print(f'---------------- pytest session info ------------------')
    print(f'Pytest current session: {pytest_status}')
    print(f'Pytest marker {session_state.test_marker_used}')

    # Provide a static HTML fallback that still shows the useful narrative even
    # when CI blocks the JS-powered pytest-html table (a real failure mode: see
    # dojo ADR 001 and mos-docker ADR 014, which motivated reporting.py).
    reports = []
    for item in session.items:
        if item.nodeid in REPORT_SUMMARIES:
            reports.append(REPORT_SUMMARIES[item.nodeid])
    reporting.write_static_report(session, reports, test_parameters.report_title)

def pytest_html_report_title(report):
    ''' A real title instead of the default bare output-filename. '''
    report.title = test_parameters.report_title

def pytest_html_results_table_html(report, data):
    '''
    Renders every step(...) call a test made (see the step fixture above) as
    an ordered list, inserted ahead of pytest's own captured-log content in
    the same expandable per-row area readers already use for "Captured
    stdout" - not a separate link or tab. Tests that never call step() just
    render their row exactly as before (no steps list, no empty artifact).
    '''
    steps = [value for name, value in report.user_properties if name == "step"]
    if steps:
        items = "".join(f"<li>{html.escape(str(s))}</li>" for s in steps)
        data.insert(0, f"<strong>Steps performed:</strong><ol>{items}</ol>")

def pytest_html_results_summary(prefix, summary, postfix, session):
    '''
    Surfaces the marker expression a run was invoked with directly in the
    report, next to the pass/fail counts - the same information
    pytest_sessionfinish already prints to the console
    (session_state.test_marker_used), just also placed where a report reader
    will actually see it.
    '''
    marker = session_state.test_marker_used or "(none - all collected tests)"
    postfix.append(f"<p>Marker expression: {html.escape(marker)}</p>")
