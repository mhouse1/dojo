'''
@brief  Hardware-independent tests for power_control.py (the NP-05B PDU helper).

This file deliberately has no module-level pytestmark: none of these tests need
a PDU, a network, or a serial port, so they run under `make swtest` and in the
Dojo-Docker CI pipeline (docs/adr/002-containerize-scaffold-validation.md) where
no bench hardware exists. What they cover is everything that can be wrong about
power_control.py without a device present:

  * the command strings and URLs each transport builds - a wrong opcode or a
    mis-encoded space silently switches nothing, or switches the wrong outlet
  * reply parsing, including the reversed bit order of a $A5 state field, which
    is the one place an off-by-one reads as "the DUT is powered" when it isn't
  * the failure paths that exist so a rejected command cannot be mistaken for an
    accepted one (power_control.py's own stated reason for SERIAL_ERROR_RE and
    the $AF check)
  * power_cycle()'s guarantee that power is restored even when the dwell is
    interrupted

What they can't cover is whether the real firmware speaks what the vendor manual
says it does - power_control.py's header calls out SERIAL_ERROR_RE, PAGER_RE and
PduSerial._login() as unconfirmed against real hardware. These tests pin the
behaviour as currently written so that confirming those strings on first use is
a visible, deliberate edit rather than a silent drift.

example: pytest test_power_control.py -vv
'''
import base64
import urllib.error

import pytest

import power_control
from power_control import PduError


# ----------------------------------------------------------------------------
# outlet validation
# ----------------------------------------------------------------------------

@pytest.mark.parametrize('outlet', range(1, power_control.OUTLET_COUNT + 1))
def test_validate_outlet_accepts_every_real_outlet(outlet):
    assert power_control._validate_outlet(outlet) == outlet


@pytest.mark.parametrize('outlet', [0, -1, power_control.OUTLET_COUNT + 1, 99])
def test_validate_outlet_rejects_out_of_range(outlet):
    '''
    Outlets are 1-based to match the front-panel labels, so 0 is the tempting
    off-by-one. It has to raise rather than wrap to outlet 5.
    '''
    with pytest.raises(PduError, match='out of range'):
        power_control._validate_outlet(outlet)


@pytest.mark.parametrize('outlet', [None, 'two', '', 1.5j])
def test_validate_outlet_rejects_non_numeric(outlet):
    with pytest.raises(PduError, match='must be an integer'):
        power_control._validate_outlet(outlet)


# ----------------------------------------------------------------------------
# $A5 state parsing
# ----------------------------------------------------------------------------

def test_parse_states_reads_rightmost_character_as_outlet_one(step):
    '''
    The bit order is the subtle part: the rightmost character of the state field
    is outlet 1, so '10000' means outlet 5 on and everything else off. Reading it
    left-to-right would report the DUT as powered when it is dark.
    '''
    step('parsing $A5 reply with only the leftmost bit set')
    states = power_control._parse_states('$A0,10000')
    assert states == {1: False, 2: False, 3: False, 4: False, 5: True}

    step('parsing $A5 reply with only the rightmost bit set')
    assert power_control._parse_states('$A0,00001')[1] is True


def test_parse_states_ignores_trailing_measurement_fields():
    '''
    Measurement-capable units append current/temperature fields this model does
    not populate; the state field is still the one to read.
    '''
    assert power_control._parse_states('$A0,11111,0.0,0.0') == {
        n: True for n in range(1, 6)}


def test_parse_states_rejects_a_truncated_reply():
    '''
    A short field means the reply was cut off, not that the unit lost an outlet.
    Accepting it would report the missing outlets as off.
    '''
    with pytest.raises(PduError, match='reported 4 outlets, expected 5'):
        power_control._parse_states('$A0,1000')


def test_parse_states_rejects_a_reply_with_no_state_field():
    with pytest.raises(PduError, match='could not find an outlet-state field'):
        power_control._parse_states('$A0,not-a-bitfield')


# ----------------------------------------------------------------------------
# PduHttp - cmd.cgi command construction and error mapping
# ----------------------------------------------------------------------------

class _FakeResponse:
    '''context-manager stand-in for what urlopen returns'''

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeUrlopen:
    '''
    Records every request and replays a scripted body, so these tests exercise
    the real URL construction and the real response handling in PduHttp._cmd()
    without a PDU or a socket.
    '''

    def __init__(self):
        self.requests = []
        self.body = b'$A0'          # a benign success reply
        self.raises = None

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        return _FakeResponse(self.body)

    @property
    def last_url(self):
        return self.requests[-1].full_url


@pytest.fixture
def fake_urlopen(monkeypatch):
    fake = _FakeUrlopen()
    monkeypatch.setattr(power_control.urllib.request, 'urlopen', fake)
    return fake


@pytest.fixture
def http_pdu():
    return power_control.PduHttp('10.0.0.5', user='admin', password='secret')


def test_http_set_outlet_sends_a3_for_that_outlet_only(fake_urlopen, http_pdu, step):
    '''
    $A3 <outlet> <state> is the single-outlet command; $A7 would hit all five.
    The space has to be percent-encoded while the $ stays literal - quoting the
    $ too would make the unit reject the command.
    '''
    step('turning outlet 2 off')
    http_pdu.outlet_off(2)
    assert fake_urlopen.last_url == 'http://10.0.0.5/cmd.cgi?cmd=$A3%202%200'

    step('turning outlet 2 on')
    http_pdu.outlet_on(2)
    assert fake_urlopen.last_url == 'http://10.0.0.5/cmd.cgi?cmd=$A3%202%201'


def test_http_reboot_outlet_sends_a4(fake_urlopen, http_pdu):
    http_pdu.reboot_outlet(3)
    assert fake_urlopen.last_url == 'http://10.0.0.5/cmd.cgi?cmd=$A4%203'


def test_http_set_all_sends_a7(fake_urlopen, http_pdu):
    http_pdu.all_off()
    assert fake_urlopen.last_url == 'http://10.0.0.5/cmd.cgi?cmd=$A7%200'
    http_pdu.all_on()
    assert fake_urlopen.last_url == 'http://10.0.0.5/cmd.cgi?cmd=$A7%201'


def test_http_outlet_states_queries_a5_and_parses_the_reply(fake_urlopen, http_pdu):
    # deliberately not a palindrome: a bitfield like '10001' would parse the same
    # way whichever end this reads from, and would pass even if the order broke
    fake_urlopen.body = b'$A0,11000'
    states = http_pdu.outlet_states()
    assert fake_urlopen.last_url == 'http://10.0.0.5/cmd.cgi?cmd=$A5'
    assert states == {1: False, 2: False, 3: False, 4: True, 5: True}


def test_http_sends_basic_auth_credentials(fake_urlopen, http_pdu):
    '''
    Credentials go in the header, never in the query string, where they would
    land in the PDU's own logs.
    '''
    http_pdu.outlet_on(1)
    expected = base64.b64encode(b'admin:secret').decode()
    assert fake_urlopen.requests[-1].get_header('Authorization') == f'Basic {expected}'
    assert 'secret' not in fake_urlopen.last_url


def test_http_raises_when_the_unit_reports_af(fake_urlopen, http_pdu):
    '''$AF is the unit's rejection code - it must not read as success.'''
    fake_urlopen.body = b'$AF'
    with pytest.raises(PduError, match='rejected command'):
        http_pdu.outlet_on(1)


def test_http_raises_when_a_web_page_comes_back_instead_of_an_api_reply(
        fake_urlopen, http_pdu):
    '''
    A unit that answers a bad login with 200 and an HTML page would otherwise
    look exactly like a successful switch.
    '''
    fake_urlopen.body = b'<HTML><body>login</body></HTML>'
    with pytest.raises(PduError, match='check credentials'):
        http_pdu.outlet_on(1)


def test_http_maps_an_http_error_to_pdu_error(fake_urlopen, http_pdu):
    fake_urlopen.raises = urllib.error.HTTPError(
        'http://10.0.0.5/cmd.cgi', 401, 'Unauthorized', None, None)
    with pytest.raises(PduError, match='HTTP 401'):
        http_pdu.outlet_on(1)


def test_http_maps_an_unreachable_unit_to_pdu_error(fake_urlopen, http_pdu):
    fake_urlopen.raises = OSError('no route to host')
    with pytest.raises(PduError, match='unreachable'):
        http_pdu.outlet_on(1)


# ----------------------------------------------------------------------------
# PduSerial - console command construction, framing and pshow parsing
# ----------------------------------------------------------------------------

class _FakeLink:
    '''
    Stand-in for serial.Serial: records what was written and hands back the next
    scripted reply. One write consumes one reply, which is what makes the pager
    test work - answering the pager is itself a write, so it pulls the next page.
    '''

    def __init__(self, replies=()):
        self.writes = []
        self._replies = list(replies)
        self._buffer = b''
        self.closed = False

    def reset_input_buffer(self):
        self._buffer = b''

    def write(self, data):
        self.writes.append(data.decode())
        if self._replies:
            self._buffer += self._replies.pop(0).encode()
        return len(data)

    @property
    def in_waiting(self):
        return len(self._buffer)

    def read(self, count):
        chunk, self._buffer = self._buffer[:count], self._buffer[count:]
        return chunk

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _instant_serial_framing(monkeypatch):
    '''
    _read_reply() frames on quiescence, so every serial command would otherwise
    cost a real SERIAL_IDLE_GAP. The framing logic still runs - only the wait
    for silence is collapsed.
    '''
    monkeypatch.setattr(power_control, 'SERIAL_IDLE_GAP', 0.0)


def _serial_pdu(replies=()):
    '''
    Build a PduSerial around a fake link without running __init__, which would
    open a real port and run the login handshake. Everything below __init__ -
    command construction, reply framing, parsing - is the real implementation.
    '''
    pdu = power_control.PduSerial.__new__(power_control.PduSerial)
    pdu.link = _FakeLink(replies)
    pdu.reply_timeout = 1.0
    return pdu


def test_serial_set_outlet_sends_pset(step):
    pdu = _serial_pdu(['ok', 'ok'])
    step('turning outlet 3 on')
    pdu.outlet_on(3)
    step('turning outlet 3 off')
    pdu.outlet_off(3)
    assert pdu.link.writes == ['pset 3 1\r', 'pset 3 0\r']


def test_serial_reboot_outlet_sends_rb():
    pdu = _serial_pdu(['ok'])
    pdu.reboot_outlet(4)
    assert pdu.link.writes == ['rb 4\r']


def test_serial_set_all_sends_ps():
    pdu = _serial_pdu(['ok', 'ok'])
    pdu.all_off()
    pdu.all_on()
    assert pdu.link.writes == ['ps 0\r', 'ps 1\r']


def test_serial_outlet_states_parses_the_pshow_table():
    '''pshow prints a table meant for a human; the parse must survive the header.'''
    table = ('\r\n'
             'Port | Name     | Status | \r\n'
             '1 | bench-a | ON  | \r\n'
             '2 | bench-b | OFF | \r\n'
             '3 | bench-c | ON  | \r\n'
             '4 | bench-d | OFF | \r\n'
             '5 | bench-e | OFF | \r\n')
    pdu = _serial_pdu([table])
    assert pdu.outlet_states() == {1: True, 2: False, 3: True, 4: False, 5: False}
    assert pdu.link.writes == ['pshow\r']


def test_serial_outlet_states_rejects_a_partial_table():
    '''
    A table cut short by a missed pager answer must not be read as "outlets 4
    and 5 are absent" - or worse, silently as off.
    '''
    pdu = _serial_pdu(['1 | a | ON | \r\n2 | b | ON | \r\n3 | c | ON | \r\n'])
    with pytest.raises(PduError, match='reported 3 outlets, expected 5'):
        pdu.outlet_states()


def test_serial_answers_the_pager_so_long_tables_arrive_whole():
    '''
    Without answering 'Press key "Enter" to continue', the rest of a pshow table
    never arrives and the parse sees a partial table.
    '''
    page_one = '1 | a | ON | \r\nPress key "Enter" to continue ...'
    page_two = '\r\n2 | b | OFF | \r\n3 | c | ON | \r\n4 | d | ON | \r\n5 | e | ON | \r\n'
    pdu = _serial_pdu([page_one, page_two])
    states = pdu.outlet_states()
    assert pdu.link.writes == ['pshow\r', '\r'], 'pager was not answered exactly once'
    assert states == {1: True, 2: False, 3: True, 4: True, 5: True}


def test_serial_raises_when_the_console_rejects_a_command():
    '''
    The console reports failure in prose with no status code, so without this
    check a refused command looks identical to an accepted one - and a test
    would power-cycle nothing while still reporting pass.
    '''
    pdu = _serial_pdu(['Access Denied'])
    with pytest.raises(PduError, match='rejected'):
        pdu.outlet_on(1)


def test_serial_raises_when_nothing_answers():
    pdu = _serial_pdu([''])
    with pytest.raises(PduError, match='check baud rate and cabling'):
        pdu.outlet_on(1)


# ----------------------------------------------------------------------------
# power_cycle and CLI helpers
# ----------------------------------------------------------------------------

class _RecordingPdu:
    '''records switching calls in order, for the power_cycle tests'''

    def __init__(self):
        self.calls = []

    def set_outlet(self, outlet, on):
        self.calls.append((outlet, on))


def test_power_cycle_switches_off_then_on(monkeypatch):
    slept = []
    monkeypatch.setattr(power_control.time, 'sleep', slept.append)
    pdu = _RecordingPdu()

    power_control.power_cycle(pdu, 2, off_seconds=7)

    assert pdu.calls == [(2, False), (2, True)]
    assert slept == [7]


def test_power_cycle_restores_power_even_when_the_dwell_is_interrupted(monkeypatch):
    '''
    An interrupt during the dwell must not leave the DUT dark for whoever walks
    up to the rack next - that's the whole reason for the finally block.
    '''
    def _interrupt(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(power_control.time, 'sleep', _interrupt)
    pdu = _RecordingPdu()

    with pytest.raises(KeyboardInterrupt):
        power_control.power_cycle(pdu, 1)

    assert pdu.calls == [(1, False), (1, True)], 'power was not restored'


def test_format_states_lists_every_outlet():
    text = power_control.format_states({1: True, 2: False})
    assert text == '  outlet 1: ON\n  outlet 2: off'


def test_confirm_all_refuses_without_yes_when_not_a_terminal(monkeypatch):
    '''
    all-on/all-off disturb every other pipeline sharing the PDU, so a CI job -
    which never has a tty - must not be able to trigger one by accident.
    '''
    monkeypatch.setattr(power_control.sys, 'stdin', type('_NoTty', (), {
        'isatty': staticmethod(lambda: False)})())

    with pytest.raises(PduError, match='pass --yes to confirm'):
        power_control._confirm_all('all-off', assume_yes=False)

    assert power_control._confirm_all('all-off', assume_yes=True) is True


@pytest.mark.parametrize('argv, expected', [
    (['status'], {'action': 'status'}),
    (['on', '1'], {'action': 'on', 'outlet': 1}),
    (['off', '1'], {'action': 'off', 'outlet': 1}),
    (['reboot', '1'], {'action': 'reboot', 'outlet': 1}),
    (['cycle', '1', '--seconds', '10'], {'action': 'cycle', 'outlet': 1, 'seconds': 10.0}),
    (['all-off', '--yes'], {'action': 'all-off', 'yes': True}),
    (['--serial', '/dev/ttyUSB1', 'status'], {'action': 'status', 'serial': '/dev/ttyUSB1'}),
])
def test_cli_parses_the_documented_invocations(argv, expected):
    '''
    Every case here is copied from readme.md's "Power control" section and
    power_control.py's own @usage block - so a CLI change that breaks a
    documented example fails here instead of in someone's terminal.
    '''
    args = power_control._build_parser().parse_args(argv)
    for name, value in expected.items():
        assert getattr(args, name) == value
