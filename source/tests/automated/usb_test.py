'''
@brief  helper script to associate USB port for known hardware based on USB serial number
        * compatible with windows and linux
        * allow serial devices to be plugged in, in any order or used on other fixtures without
        having to check which port it is assigned to

@usage  simply run this script to determine your hardware info

note: in some cases a HW set may report the same serial numbers, in this case you should use
ID_PATH and udev rules instead (only possible in linux), this script cant do that for you
'''

def show_serial_info():
    '''
    Print serial number and serial port name for all ports
    return values in detected_serial_dict

    for example: {'MYSERIALNUM': 'COM3'}
    '''
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    detected_serial_dict = {}
    for port, desc, hwid in sorted(ports):
        try:
            serial_number = hwid.split('SER=')[1][:8]
            print("{}: {} Serial Number={}".format(port, desc, serial_number))
            detected_serial_dict[serial_number] = port
        except:
            # we dont care about ttyAMA or bluetooth, etc.
            print(f'skipped {port, desc, hwid}')
    print(detected_serial_dict)
    return detected_serial_dict

def assign_known_hardware():
    '''
    use known hardware serial numbers to determine which serial port it is assigned to

    For example:
        For serial number: MYSERIALNUM
            checking if in: MYHARDWARENAME
            checking if in: MYOTHERHARDWARENAME
            detected: MYSERIALNUM as MYHARDWARENAME
    '''

    detected_serial_dict = show_serial_info()

    # Empty in the scaffold so nothing here can be mistaken for real seed
    # data. Use show_serial_info() to find your hardware's serial numbers,
    # then fill this in, e.g.:
    #   known_hardware = {'my-board-console': ['FTCFPK30', 'FT9LDIE3']}
    known_hardware = {}
    assigned_port = {}
    for serial_number in detected_serial_dict.keys():
        print(f'For serial number: {serial_number}')
        for hardware in known_hardware.keys():
            print(f'\t checking if in: {hardware}')
            if serial_number[:] in str(known_hardware[hardware]):
                print(f'\t detected: {serial_number} as {hardware}')
                assigned_port[hardware] = detected_serial_dict[serial_number]
                break
    print(assigned_port)
    return assigned_port

if __name__ == '__main__':
    show_serial_info()

    # enable for testing assign_known_hardware()
    # assign_known_hardware()
    pass
