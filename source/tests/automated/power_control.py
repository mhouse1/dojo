'''
@brief  control a Synaccess netBooter NP-05B network-switched PDU

        Two transports, identical methods on both, so a test neither knows nor
        cares which one it got:
          * PduHttp   - local IP ethernet via the cmd.cgi HTTP API (stdlib only)
          * PduSerial - USB serial console, 9600 8N1 (pyserial, already pinned)

        Both expose:
          set_outlet(n, on)   control one port, leaving the others untouched
          outlet_on(n) / outlet_off(n)
          reboot_outlet(n)    off, dwell, back on - dwell is the PDU's own rbt value
          all_on() / all_off()    everything at once - see the warning on set_all()
          set_all(on)
          outlet_states()     {1: True, 2: False, ...}

        See docs/research/001-np-05b-network-controlled-power-outlet.md for the
        command set this is built on and the rig design it supports.

@usage  from a test:
            import power_control
            with power_control.PduHttp('192.168.1.100') as p:
                p.outlet_off(1)             # cut power to the DUT on outlet 1
                p.outlet_on(1)              # restore it
                print(p.outlet_states())

        from the command line:
            uv run python power_control.py status
            uv run python power_control.py on 1
            uv run python power_control.py off 1
            uv run python power_control.py reboot 1
            uv run python power_control.py cycle 1 --seconds 10
            uv run python power_control.py all-off --yes
            uv run python power_control.py --serial /dev/ttyUSB1 status

        credentials come from --user/--password, or the DOJO_POWER_* env vars,
        falling back to the unit's factory admin/admin - change those on
        commissioning and set DOJO_POWER_PASSWORD instead of passing it on the
        command line, where it would land in shell history and CI logs.

note:   this module is named for what it does rather than for the device class -
        "PDU" collides with Protocol Data Unit, which is the reading an embedded
        engineer would reach for first in a directory of transport helpers. The
        classes keep the Pdu prefix because next to outlet_off() and all_on()
        there is nothing to confuse them with.

        The HTTP transport has been exercised against a simulated cmd.cgi. The
        serial transport has NOT been run against real hardware: the strings in
        SERIAL_ERROR_RE and PAGER_RE, and the login handshake in
        PduSerial._login(), are taken from the vendor manual and should be
        confirmed on first use. They are collected at the top of this module so
        that confirming them is an edit in one place.
'''
import argparse
import base64
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# NP-05B is the 5-outlet model; NP-02B is 2. Guarding on this turns a typo into
# a clear error instead of a silent no-op or an unintended outlet switching.
OUTLET_COUNT = 5

DEFAULT_HOST = os.environ.get('DOJO_POWER_HOST', '192.168.1.100')
DEFAULT_USER = os.environ.get('DOJO_POWER_USER', 'admin')
DEFAULT_PASSWORD = os.environ.get('DOJO_POWER_PASSWORD', 'admin')
DEFAULT_BAUDRATE = 9600

# Serial reply framing. read_until(b'>') does NOT work here: the unit prefixes
# banner and menu lines with '>', so it returns a fragment of the first line
# rather than the whole reply - against a real pshow table it stops inside the
# banner, before any outlet row. Frame on quiescence instead: a reply is
# complete once the device has been silent for SERIAL_IDLE_GAP.
SERIAL_IDLE_GAP = 0.25
SERIAL_REPLY_TIMEOUT = 5.0
SERIAL_POLL = 0.02

# Long tables page with 'Press key "Enter" to continue ...' and the rest of the
# output never arrives unless the pager is answered.
PAGER_RE = re.compile(r'press\s+key.*continue', re.IGNORECASE)
MAX_PAGER_ANSWERS = 10

# The serial console reports failure in prose, with no status code, so a
# rejected command otherwise looks exactly like an accepted one - which would
# leave a test power-cycling nothing while still passing. Exact wording varies
# by firmware; extend this if your unit phrases it differently.
SERIAL_ERROR_RE = re.compile(
    r'(access denied|permission denied|not allowed|invalid|unknown command|'
    r'please login|login failed|bad password|error)', re.IGNORECASE)


class PduError(Exception):
    '''raised when the PDU rejects a command or is unreachable'''


def _validate_outlet(outlet):
    '''outlets are 1-based on this hardware, matching the front-panel labels'''
    try:
        outlet = int(outlet)
    except (TypeError, ValueError) as e:
        raise PduError(f'outlet must be an integer, got {outlet!r}') from e
    if not 1 <= outlet <= OUTLET_COUNT:
        raise PduError(f'outlet {outlet} out of range - this unit has {OUTLET_COUNT}')
    return outlet


def _check_outlet_count(states, source):
    '''
    A short or over-long state map means the reply was truncated or misaligned,
    not that the unit grew or lost outlets. Catching it here stops a partial
    parse from being read as "outlet 5 is off".
    '''
    if len(states) != OUTLET_COUNT:
        raise PduError(
            f'{source} reported {len(states)} outlets, expected {OUTLET_COUNT} - '
            f'reply truncated, or set OUTLET_COUNT for a different model')
    return states


def _parse_states(payload):
    '''
    Pull the outlet-state bitfield out of a $A5 reply and return {outlet: bool}.

    The reply is a comma-separated record whose first field is the state string;
    on measurement-capable units further fields carry current and temperature,
    which this model does not populate. The rightmost character is outlet 1, so
    the string is reversed before enumerating.
    '''
    cleaned = payload.replace('$A0', '').strip()
    for field in cleaned.split(','):
        field = field.strip()
        if field and set(field) <= {'0', '1'}:
            states = {i + 1: c == '1' for i, c in enumerate(reversed(field))}
            return _check_outlet_count(states, '$A5 reply')
    raise PduError(f'could not find an outlet-state field in reply: {payload!r}')


class PduHttp:
    '''NP-05B over local IP ethernet, using the cmd.cgi HTTP API'''

    def __init__(self, host=DEFAULT_HOST, user=DEFAULT_USER,
                 password=DEFAULT_PASSWORD, timeout=5):
        self.host = host
        self.timeout = timeout
        token = base64.b64encode(f'{user}:{password}'.encode()).decode()
        self.headers = {'Authorization': f'Basic {token}'}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self):
        '''nothing to release - present so both transports close the same way'''

    def _cmd(self, command):
        # safe='$' keeps the command prefix literal; the spaces between the
        # command and its arguments still have to be percent-encoded
        quoted = urllib.parse.quote(command, safe='$')
        url = f'http://{self.host}/cmd.cgi?cmd={quoted}'
        request = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode(errors='replace').strip()
        except urllib.error.HTTPError as e:
            raise PduError(f'PDU at {self.host} returned HTTP {e.code} for {command!r} '
                           f'- check credentials') from e
        except OSError as e:
            raise PduError(f'PDU at {self.host} unreachable: {e}') from e
        if '$AF' in body:
            raise PduError(f'PDU rejected command {command!r}: {body}')
        # Success is inferred from the absence of $AF. If a unit ever answers a
        # bad login with 200 and an HTML page instead of 401, that would read as
        # success here - worth confirming against real hardware.
        if '<html' in body.lower():
            raise PduError(f'PDU at {self.host} returned a web page, not an API reply '
                           f'- check credentials')
        return body

    def set_outlet(self, outlet, on):
        '''switch a single outlet, leaving the other four untouched'''
        outlet = _validate_outlet(outlet)
        return self._cmd(f'$A3 {outlet} {1 if on else 0}')

    def reboot_outlet(self, outlet):
        '''off, dwell for the PDU's configured reboot duration, back on'''
        outlet = _validate_outlet(outlet)
        return self._cmd(f'$A4 {outlet}')

    def set_all(self, on):
        '''
        Switch every outlet at once.

        WARNING: where several pipelines share one PDU - the five-pipeline rig
        in the research doc - this hits every other pipeline's DUT as well as
        your own. Prefer set_outlet() unless you own the whole unit.
        '''
        return self._cmd(f'$A7 {1 if on else 0}')

    def outlet_states(self):
        return _parse_states(self._cmd('$A5'))

    # convenience wrappers - the same four names exist on PduSerial
    def outlet_on(self, outlet):
        return self.set_outlet(outlet, True)

    def outlet_off(self, outlet):
        return self.set_outlet(outlet, False)

    def all_on(self):
        '''every outlet on - see the warning on set_all()'''
        return self.set_all(True)

    def all_off(self):
        '''every outlet off - see the warning on set_all()'''
        return self.set_all(False)


class PduSerial:
    '''
    NP-05B over the USB serial console - no network involved at all.

    Useful for a single-agent bench that keeps the PDU off the network, and as
    the recovery path when the unit's IP configuration is wrong or unknown.
    '''

    def __init__(self, port, baudrate=DEFAULT_BAUDRATE, user=DEFAULT_USER,
                 password=DEFAULT_PASSWORD, timeout=SERIAL_REPLY_TIMEOUT):
        # imported here, not at module scope, so the HTTP transport and the CLI
        # stay usable if pyserial isn't installed
        import serial
        self.link = None
        self.reply_timeout = timeout
        try:
            # 9600 8N1, no flow control - the unit's factory default. The port's
            # own timeout is just the poll interval; _read_reply() does the
            # framing and honours self.reply_timeout.
            self.link = serial.Serial(port, baudrate, timeout=SERIAL_POLL)
        except serial.SerialException as e:
            raise PduError(f'could not open serial port {port}: {e}') from e
        try:
            self._login(user, password)
        except Exception:
            # the caller never receives this object, so nobody else could close
            # it - release the port here rather than leaking it until GC
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self):
        if getattr(self, 'link', None) is not None:
            self.link.close()
            self.link = None

    def _read_reply(self):
        '''
        Read one reply, framing it on quiescence rather than on a prompt
        character, and answering the pager so long tables arrive whole.

        See the SERIAL_IDLE_GAP comment for why matching on '>' does not work.
        '''
        deadline = time.monotonic() + self.reply_timeout
        chunks = []
        pages = 0
        answered_upto = 0
        last_rx = time.monotonic()
        while time.monotonic() < deadline:
            waiting = self.link.in_waiting
            if waiting:
                chunks.append(self.link.read(waiting))
                last_rx = time.monotonic()
                text = b''.join(chunks).decode(errors='replace')
                # only scan what arrived since the last answer, so one pager
                # prompt is not answered over and over
                if pages < MAX_PAGER_ANSWERS and PAGER_RE.search(text, answered_upto):
                    self.link.write(b'\r')
                    pages += 1
                    answered_upto = len(text)
                continue
            if time.monotonic() - last_rx >= SERIAL_IDLE_GAP:
                break
            time.sleep(SERIAL_POLL)
        return b''.join(chunks).decode(errors='replace')

    def _cmd(self, command, expect_reply=True):
        self.link.reset_input_buffer()
        self.link.write(f'{command}\r'.encode())
        reply = self._read_reply()
        if expect_reply and not reply.strip():
            raise PduError(f'no response to {command!r} - check baud rate and cabling')
        if SERIAL_ERROR_RE.search(reply):
            raise PduError(f'PDU rejected {command!r}: {reply.strip()[:200]}')
        return reply

    def _login(self, user, password):
        '''
        Firmware differs on whether "login" takes arguments or prompts for them,
        so try the single-line form and fall back to answering the prompts.

        A rejected login raises, via _cmd()'s error check. Without that, every
        later pset would be quietly refused and a test would power-cycle nothing
        while still reporting pass.
        '''
        self._cmd('', expect_reply=False)
        sent = f'login {user} {password}'
        reply = self._cmd(sent, expect_reply=False)
        # drop the echoed command before looking for a prompt, so a password
        # that happens to contain 'password' cannot be mistaken for one
        tail = reply.replace(sent, '', 1)
        if re.search(r'(user\s*name|login\s*name|password)', tail, re.IGNORECASE):
            self._cmd(user, expect_reply=False)
            self._cmd(password, expect_reply=False)

    def set_outlet(self, outlet, on):
        '''switch a single outlet, leaving the other four untouched'''
        outlet = _validate_outlet(outlet)
        return self._cmd(f'pset {outlet} {1 if on else 0}')

    def reboot_outlet(self, outlet):
        outlet = _validate_outlet(outlet)
        return self._cmd(f'rb {outlet}')

    def set_all(self, on):
        '''
        Switch every outlet at once.

        WARNING: where several pipelines share one PDU, this hits every other
        pipeline's DUT as well as your own. Prefer set_outlet().

        Note also that the vendor help menu marks pset as available under
        Restricted Access Mode but not ps, so on a restricted account this can
        fail where set_outlet() succeeds.
        '''
        return self._cmd(f'ps {1 if on else 0}')

    def outlet_states(self):
        '''
        pshow prints a table meant for a human at a terminal, so this parses the
        "Port | Name | Status | ..." rows. Prefer PduHttp.outlet_states() where
        both transports are available.
        '''
        states = {}
        for line in self._cmd('pshow').splitlines():
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 3 or not parts[0].isdigit():
                continue
            states[int(parts[0])] = parts[2].lower().startswith('on')
        if not states:
            raise PduError('could not parse any outlet rows from pshow output')
        return _check_outlet_count(states, 'pshow')

    def outlet_on(self, outlet):
        return self.set_outlet(outlet, True)

    def outlet_off(self, outlet):
        return self.set_outlet(outlet, False)

    def all_on(self):
        '''every outlet on - see the warning on set_all()'''
        return self.set_all(True)

    def all_off(self):
        '''every outlet off - see the warning on set_all()'''
        return self.set_all(False)


def power_cycle(pdu, outlet, off_seconds=5):
    '''
    Host-timed power cycle: off, wait, on - with the dwell measured here rather
    than by the PDU's own reboot duration.

    Use this when a test needs a specific dwell; use pdu.reboot_outlet() when
    the PDU's configured duration is fine. Note the dwell is only as accurate as
    the host's scheduling and the link's latency, so treat sub-second values as
    uncharacterised unless you have scoped them (see the research doc's
    brown-out section).

    Power is restored in a finally block: an interrupt during the dwell must not
    leave the DUT dark for whoever walks up to the rack next.
    '''
    pdu.set_outlet(outlet, False)
    try:
        time.sleep(off_seconds)
    finally:
        pdu.set_outlet(outlet, True)


def format_states(states):
    '''one line per outlet, for the CLI's status output'''
    return '\n'.join(f'  outlet {n}: {"ON" if on else "off"}'
                     for n, on in sorted(states.items()))


def _confirm_all(action, assume_yes):
    '''
    all-on and all-off switch every outlet, so on a shared rig they disturb
    other pipelines' targets. Require an explicit --yes when nobody is watching.
    '''
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        raise PduError(
            f'{action} switches all {OUTLET_COUNT} outlets and would disturb any '
            f'other pipeline sharing this PDU - pass --yes to confirm')
    answer = input(f'{action} switches ALL {OUTLET_COUNT} outlets. Continue? [y/N] ')
    return answer.strip().lower() in ('y', 'yes')


def _build_parser():
    parser = argparse.ArgumentParser(
        description='control a Synaccess NP-05B switched PDU',
        epilog='credentials also read from DOJO_POWER_HOST/USER/PASSWORD',
    )
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help=f'PDU address for the ethernet transport (default {DEFAULT_HOST})')
    parser.add_argument('--serial', metavar='PORT',
                        help='use the USB serial console instead, e.g. /dev/ttyUSB1 or COM3')
    parser.add_argument('--baudrate', type=int, default=DEFAULT_BAUDRATE,
                        help=f'serial baud rate (default {DEFAULT_BAUDRATE})')
    parser.add_argument('--user', default=DEFAULT_USER)
    parser.add_argument('--password', default=DEFAULT_PASSWORD)

    sub = parser.add_subparsers(dest='action', required=True)
    for name, help_text in (('on', 'turn one outlet on'),
                            ('off', 'turn one outlet off'),
                            ('reboot', 'reboot one outlet')):
        p = sub.add_parser(name, help=help_text)
        p.add_argument('outlet', type=int, help=f'outlet number, 1 to {OUTLET_COUNT}')
    cycle = sub.add_parser('cycle', help='off, wait, on - with a host-timed dwell')
    cycle.add_argument('outlet', type=int, help=f'outlet number, 1 to {OUTLET_COUNT}')
    cycle.add_argument('--seconds', type=float, default=5.0, help='dwell time (default 5)')
    for name, help_text in (('all-on', 'turn every outlet on'),
                            ('all-off', 'turn every outlet off')):
        p = sub.add_parser(name, help=f'{help_text} - affects other pipelines on a shared PDU')
        p.add_argument('--yes', action='store_true',
                       help='confirm; required when not run from a terminal')
    sub.add_parser('status', help='show the state of every outlet')
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if args.serial:
        connection = PduSerial(args.serial, baudrate=args.baudrate,
                               user=args.user, password=args.password)
        where = args.serial
    else:
        connection = PduHttp(args.host, user=args.user, password=args.password)
        where = args.host

    with connection as pdu:
        if args.action == 'status':
            # read before printing the header, so a failure doesn't leave a
            # dangling address line above the error
            states = pdu.outlet_states()
            print(f'{where}:')
            print(format_states(states))
        elif args.action == 'on':
            pdu.outlet_on(args.outlet)
            print(f'outlet {args.outlet} on')
        elif args.action == 'off':
            pdu.outlet_off(args.outlet)
            print(f'outlet {args.outlet} off')
        elif args.action == 'reboot':
            pdu.reboot_outlet(args.outlet)
            print(f'outlet {args.outlet} rebooted')
        elif args.action == 'cycle':
            power_cycle(pdu, args.outlet, args.seconds)
            print(f'outlet {args.outlet} cycled, {args.seconds}s off')
        elif args.action in ('all-on', 'all-off'):
            if not _confirm_all(args.action, getattr(args, 'yes', False)):
                print('aborted')
                return 1
            if args.action == 'all-on':
                pdu.all_on()
                print('all outlets on')
            else:
                pdu.all_off()
                print('all outlets off')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except PduError as e:
        sys.exit(f'error: {e}')
