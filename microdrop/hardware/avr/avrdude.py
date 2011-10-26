"""
Copyright 2011 Ryan Fobel and Christian Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import os

from subprocess import Popen, PIPE, CalledProcessError
from hardware.serial_device import SerialDevice, ConnectionError
from hardware import hardware_path
from utility import path


class FirmwareError(Exception):
    pass


class AvrDude(SerialDevice):
    def __init__(self):
        if os.name == 'nt':
            self.avrdude = hardware_path() / path('avr') / path('avrdude.exe')
        else:
            self.avrdude = hardware_path() / path('avr') / path('avrdude')
        if not self.avrdude.exists():
            raise FirmwareError('avrdude not installed')
        self.avrconf = hardware_path() / path('avr') / path('avrdude.conf')
        self.port = self.get_port()
        print 'avrdude successfully connected on port: ', self.port

    def _run_command(self, flags, verbose=False):
        config = dict(avrdude=self.avrdude, avrconf=self.avrconf)

        cmd = ['%(avrdude)s'] + flags
        cmd = [v % config for v in cmd]
        if verbose:
            print ' '.join(cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if p.returncode:
            raise ConnectionError(stderr)
        return stdout, stderr

    def flash(self, hex_path):
        hex_path = path(hex_path)
        flags = ['-c', 'stk500v2', '-b', '115200', '-p', 'atmega2560',
                    '-P', self.port,
                    '-U', 'flash:w:%s' % hex_path.name, 
                    '-C', '%(avrconf)s']

        try:
            cwd = os.getcwd()
            os.chdir(hex_path.parent)
            stdout, stderr = self._run_command(flags)
        finally:
            os.chdir(cwd)
        return stdout, stderr

    def test_connection(self, port):
        flags = ['-c', 'stk500v2', '-b', '115200', '-p', 'atmega2560',
                    '-P', port,
                    '-C', '%(avrconf)s', '-n']
        try:
            self._run_command(flags)
        except (ConnectionError, CalledProcessError):
            return False
        return True