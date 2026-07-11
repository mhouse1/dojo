'''
@brief  Example SSH-reachability tests against the target under test.

This file is the working example of the scaffold's "one file per feature"
convention (see readme.md "Adding a new test"): one test_*.py per feature
area, module-level pytestmark instead of decorating every test, and the
ssh_client/step fixtures instead of hand-rolled connection management.

Copy this file's shape when adding a real feature area, then delete this one
once real feature tests exist - it's a worked template, not a permanent test.

example: pytest test_example_ssh.py -vv -m hardware --target-host 192.168.1.100
'''
import pytest
import coms

# every test in this file needs the real target - apply once here rather than
# repeating @pytest.mark.hardware on each one (and risk a future test forgetting it)
pytestmark = pytest.mark.hardware

@pytest.mark.smokeTest
def test_ssh_reachable(ssh_client, step):
    step("ran: echo ping")
    output = coms.sshCommand(ssh_client, "echo ping")
    step(f"result: {output.strip()!r}")
    assert output.strip() == "ping"

def test_ssh_hostname_reported(ssh_client, step):
    step("ran: hostname")
    output = coms.sshCommand(ssh_client, "hostname")
    step(f"result: {output.strip()!r}")
    assert output.strip() != "", "hostname command returned nothing"

def test_ssh_command_exit_code_is_checked(ssh_client, step):
    '''
    Confirms sshCommandWait actually enforces exit codes against this target -
    a command guaranteed to fail should be reported as a failure, not silently pass.
    '''
    step("ran: false, expecting sshCommandWait to raise on the non-zero exit code")
    with pytest.raises(AssertionError):
        coms.sshCommandWait(ssh_client, "false")
