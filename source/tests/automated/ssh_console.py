'''
@brief  SSH to the target under test and live-tail a systemd service's journal
        until closed.

@usage  uv run python ssh_console.py
        connects via coms.sshCreate() - DOJO_SSH_PASSWORD must be set (see
        readme.md "SSH credentials") - and streams `journalctl -u <SERVICE> -f`
        Ctrl+C exits
'''
import os
import sys

import coms
import test_parameters

# Placeholder - point this at whichever systemd service on your target you
# want to tail during development.
SERVICE = 'your-service.service'

if __name__ == '__main__':
    if not os.environ.get('DOJO_SSH_PASSWORD'):
        sys.exit(
            'DOJO_SSH_PASSWORD is not set - export it before running this '
            '(see readme.md "SSH credentials")'
        )

    host, user = test_parameters.target_host, test_parameters.target_user
    print(f'Connecting to {user}@{host} to stream {SERVICE} journal (Ctrl+C to exit)')

    ssh = coms.sshCreate(host, 22, user)
    try:
        _stdin, stdout, _stderr = ssh.exec_command(f'journalctl -u {SERVICE} -n 50 -f --no-pager')
        for line in iter(stdout.readline, ''):
            print(line, end='')
    except KeyboardInterrupt:
        print('\nClosing.')
    finally:
        coms.sshFree(ssh)
