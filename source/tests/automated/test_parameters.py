'''
I like to use a test_parameters file so all test parameters are in one place
it also allows us to easily use it during tests

This file holds configuration mirrored from CLI options (or fixed constants) -
values that are read once and don't change for the rest of a session. Mutable
state that changes *during* a run (e.g. whether a test blocker has fired) lives
in session_state.py instead - keeping "what was this suite told to do" separate
from "what has happened so far this run" is the whole reason for the split.
'''
import os,sys,datetime, socket
this_script_location = os.path.dirname(os.path.realpath(__file__))
parent_folder = os.path.dirname(os.path.dirname(this_script_location))

# dont forget to also update the CHANGELOG.md file so we can track chages to the test suite
automated_test_version = '0.0.2'
time_date = datetime.date.today()
time_now = f"{datetime.datetime.now()}"

# title used by both conftest.py's pytest_html_report_title and reporting.py's
# static-report fallback - kept in one place so the two report surfaces can't
# drift apart into two different titles
report_title = "Embedded HIL Test Report"

################ define test fixture default parameters
# for serial ports linux and windows have different syntax
# for linux to show serial ports: ls /dev/ttyUSB*
# for windows use device manager
# or just run the python usb_test.py script
if sys.platform == 'win32':
    is_windows_host = True
    my_serial_port = 'COM3'
else:
    is_windows_host = False
    my_serial_port = '/dev/ttyUSB0'

# it may be useful to know the hostname to determine which machine this test is running on
hostname = socket.gethostname()

# target under test's address/user; override via --target-host/--target-user
target_host = '192.168.1.100'
target_user = 'root'

if __name__ == '__main__':
    print(f'is_windows_host {is_windows_host}')
    print(f'parent folder holding this script: {parent_folder}')
    print(f'time today: {time_date}')
    print(f'time now: {time_now}')
