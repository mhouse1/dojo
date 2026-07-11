'''
@brief      tools for communication with an embedded target via SSH and serial

Single "transport helpers" module - every test calls into this instead of
making raw paramiko/pyserial calls directly, so the awkward edge cases (a
reboot severing the SSH session mid-command, retrying a flaky ping) live in
one place and tests read declaratively (ADR 001).
'''
import paramiko, sys, os, re, time, platform, subprocess
from scp import SCPClient
import serial
import test_parameters

FAILURE_PATTERNS = re.compile(
    r"(traceback|segmentation fault|failed to|failed:|fatal|exception|error:)",
    re.IGNORECASE,
)


def extract_startup_failure_lines(log_text):
    '''Returns the lines of log_text that look like a startup/crash failure indicator.'''
    if not log_text:
        return []
    return [line.strip() for line in log_text.splitlines() if FAILURE_PATTERNS.search(line)]

def sshCreate(hostname, port, username, password=None):
    '''
    if password isn't passed explicitly, falls back to the DOJO_SSH_PASSWORD env var so
    callers (and CI) aren't forced to hardcode credentials in test code
    '''
    password = password if password is not None else os.environ.get('DOJO_SSH_PASSWORD')
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
    client.connect(hostname,port,username,password, timeout = 60.0)
    return client


def sshFree(ssh = None):
    '''
    Prefer the ssh_client fixture (conftest.py) over calling this directly in new
    test code - it calls this in fixture teardown automatically, including on
    test failure, which is a structural guarantee rather than something every
    test has to remember to do correctly in its own try/finally.
    '''
    if ssh:
        ssh.close()

def sshProgress(filename,size,sent):
    '''callback function used by sshUPload to show ssh scp progress'''
    percent = (float(sent)/float(size))*100
    if percent.is_integer():
        sys.stdout.write("%s\'s progress: %.2f%%  \r" % (filename,percent))

def sshUpload(ssh, file_location, file_destination):
    '''Uploads a file using the ssh connection using SCP
    where file_location and file_destination is full file path /filepath/file.txt'''
    try:
        scp = SCPClient(ssh.get_transport(), progress = sshProgress, socket_timeout = 30.0)
        scp.put(file_location, file_destination)
        scp.close()
    except Exception as e:
        print(f'ssh upload failed to upload: {file_location} to {file_destination}: {e}')
    else:
        print(f' ssh upload successful to: {file_destination}')

def sshCommand(ssh,cmd,timeout= 60):
    stdin, _stdout, _stderr = ssh.exec_command(cmd,timeout=timeout) #Non-blocking call
    output = _stdout.read().decode()
    return output

def sshCommandWait(ssh,cmd,timeout=60):
    '''
    execute ssh command and wait until command finishes
    this may be useful for a command that takes more time to finish
    '''
    stdin, _stdout, _stderr = ssh.exec_command(cmd,timeout=timeout) #Non-blocking call
    exit_code = _stdout.channel.recv_exit_status()
    if exit_code == 0:
        print(f'finished ssh command: {cmd}')
    else:
        assert False, f'ssh command finished with error {exit_code} while running command: {cmd}'

def sshReboot(ssh, cmd='reboot'):
    '''
    Issue reboot (or another disruptive command that never returns a clean exit
    status) over an existing connection and treat the resulting connection drop
    as success rather than a failure.

    Do not use sshCommandWait() for this: the remote side tears down sshd before
    it can send an exit status back, so recv_exit_status() either hangs or raises
    instead of returning 0 - sshCommandWait would misreport that as a failed
    command. Deliberately does not call ssh.close(): the transport is already
    severed by the time this returns, and closing an already-dead transport is
    unnecessary and can itself raise.
    '''
    try:
        ssh.exec_command(cmd, timeout=10)
        # give the remote shell a moment to actually act on the command before
        # the caller starts polling for the unit to go down
        time.sleep(2)
    except Exception as e:
        print(f'connection dropped as expected during "{cmd}": {e}')

def _ping_once(address):
    '''sends a single ping, platform-agnostic (windows uses -n, everything else uses -c)'''
    count_flag = '-n' if platform.system().lower() == 'windows' else '-c'
    result = subprocess.run(
        ['ping', count_flag, '1', address],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0

def check_ping(address):
    if _ping_once(address):
        assert True, 'Ping successful'
        return True
    else:
        assert False, 'Ping Failed'

def check_ping_until_timeout(address, timeout=20):
    timeout = time.time() + timeout
    while time.time() < timeout:
        print(f'{test_parameters.time_now} checking ping at: {address} ')
        if _ping_once(address):
            print(f'{test_parameters.time_now} Ping Successful')
            return True
        else:
            print('Ping failed, trying again')
            time.sleep(5)
    assert False, 'Ping failed, timed-out while trying'

def wait(seconds = 60, why =""):
    '''
    wait and print status so we know something is happening - rather than a
    bare time.sleep(). Lives here (not test_parameters.py) alongside the
    suite's other waiting/polling helpers (check_ping_until_timeout, etc).
    '''
    timeout = time.time() + seconds
    while time.time() < timeout:
        print(why,f"; waited {round(abs(timeout - seconds - time.time()),2) } of {seconds} seconds")
        time.sleep(5)

def serial_read(serial, timeout):
    if serial.inWaiting() > 0:
        data = serial.readline().decode('utf-8', errors='ignore')
        print(data[:-2]) # ignore last two chars which is likely \r\n

def serial_monitor(serial_port = 'undefined', expected_text = 'hello world', serial_text_scan_timeout = 30):
    '''watches a serial port for expected_text until timeout, printing any other lines seen'''
    ser = None
    try:
        ser = serial.Serial(port = serial_port, baudrate=115200,bytesize=8,parity='N',stopbits=1,timeout=1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f'connected to : {serial_port}')

        scantimeout = time.time() + serial_text_scan_timeout
        while time.time() < scantimeout:
            data = ser.readlines()
            if expected_text in str(data):
                return True
            for value in data:
                print('serial data',value)
        return False
    finally:
        print('serial_monitor() closing...')
        if ser is not None:
            ser.close()
