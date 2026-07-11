'''
@brief  interactive serial console for the target's UART

        resolves the port via usb_test.assign_known_hardware() instead of a
        hardcoded /dev/ttyUSB0, so it keeps working whichever ttyUSBn the
        kernel assigns this session.

@usage  uv run python serial_console.py
        prints anything received on the port; anything typed is sent over TX
        Ctrl+] exits (pyserial miniterm default)
'''
import sys

import usb_test

# Placeholder - match one of usb_test.py's known_hardware keys once you've
# filled it in for your board.
HARDWARE_NAME = 'your-board-console'
BAUDRATE = 115200

def resolve_port():
    known_hardware = usb_test.assign_known_hardware()
    if HARDWARE_NAME not in known_hardware:
        sys.exit(f"'{HARDWARE_NAME}' not detected - is the cable plugged in?")
    return known_hardware[HARDWARE_NAME]

if __name__ == '__main__':
    port = resolve_port()
    print(f'Opening interactive console on {port} @ {BAUDRATE} baud (Ctrl+] to exit)')

    from serial.tools import miniterm
    miniterm.main(default_port=port, default_baudrate=BAUDRATE)
