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

class ConnectionError(Exception):
    pass


class SerialDevice(object):
    def get_port(self):
        port = None
        if os.name == 'nt':
            # Windows
            for i in range(0,31):
                test_port = "COM%d" % i
                if self.test_connection(test_port):
                    port = test_port
                    break
        else:
            # Assume Linux (Ubuntu)...
            for tty in path('/dev').walk('ttyUSB*'):
                if self.test_connection(tty):
                    port = tty
                    break
        if port is None:
            raise ConnectionError('could not connect to serial device.')
        return port


    def test_connection(self, port):
        raise NotImplementedError