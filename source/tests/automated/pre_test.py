'''
@brief  Fixture health checks. Run first and marked isTestFixtureOk: if any of
        these fail, the blocker mechanism (conftest.py) aborts the rest of the
        session instead of letting every dependent test time out individually.
'''
import os
import pytest

import coms, test_parameters

def test_changelog_version_matches():
    '''
    Catches a forgotten update: test_parameters.automated_test_version and
    CHANGELOG.md's newest ("## " headed) entry should always agree - otherwise
    either the version was bumped without a changelog entry, or vice versa.
    No hardware needed, so this always runs (including under make swtest).
    '''
    changelog_path = os.path.join(test_parameters.this_script_location, 'CHANGELOG.md')
    with open(changelog_path) as f:
        for line in f:
            if line.startswith('## '):
                assert test_parameters.automated_test_version in line, (
                    f"test_parameters.automated_test_version "
                    f"({test_parameters.automated_test_version!r}) not found in "
                    f"CHANGELOG.md's newest entry ({line.strip()!r}) - did you forget "
                    f"to bump one of them?"
                )
                break
        else:
            assert False, "no '## ' version heading found in CHANGELOG.md"

@pytest.mark.isTestFixtureOk
def test_pre_test(step):
    '''
    make sure the host is setup correctly
    dont bother running tests if this test fails

    example: python -m pytest pre_test.py -s -vv -m isTestFixtureOk
    '''

    step(f"Automated Test Version: {test_parameters.automated_test_version}")

    # test if these libraries are available
    step("checking paramiko, serial, subprocess are importable")
    import paramiko, serial, subprocess

    # test tool versions
    import sys
    # check python version
    step(f"checking python major version is 3 (got {sys.version_info[0]})")
    if not sys.version_info[0] == 3:
        assert False, "python3 required but not detected"

@pytest.mark.isTestFixtureOk
@pytest.mark.hardware
def test_target_host_reachable(target_host, step):
    '''
    Fail fast, here, with a clear message, if the unit under test isn't reachable at all -
    rather than have every individual hardware test in the suite time out and fail with a
    less obvious connection error. isTestFixtureOk means a failure here aborts the rest of
    the session (see conftest.py's blocker mechanism).

    example: pytest pre_test.py -s -vv -m isTestFixtureOk --target-host 192.168.1.100
    '''
    step(f"pinging {target_host} until reachable (timeout 30s)")
    coms.check_ping_until_timeout(target_host, timeout=30)
