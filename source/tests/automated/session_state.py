'''
Mutable runtime state shared across a single pytest session - distinct from
test_parameters.py, which mirrors CLI-supplied configuration that doesn't
change once a session starts. Everything in this file DOES change during a
run: it's set by hooks/fixtures in conftest.py and read elsewhere to make
decisions (e.g. whether to abort the rest of the session).
'''

# set via --ignore_test_blockers; lets a failed isTestFixtureOk-marked test's
# blocker be ignored instead of aborting the rest of the session
ignore_blockers = False

# set to True when a blocker test fails (see conftest.pytest_runtest_makereport)
# to stop the rest of the suite from running (see conftest.setup_test)
blocker_failed = False

# the -m marker expression the session was invoked with, recorded for the
# end-of-session summary (see conftest.pytest_sessionfinish)
test_marker_used = ''
