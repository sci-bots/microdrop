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

from avr.serial_device import SerialDevice, ConnectionError
from utility import is_float


class DmfControlBoardInfo(SerialDevice):
    def __init__(self):
        self.port = None
        try:
            from hardware.dmf_control_board.device import DmfControlBoard
        except ImportError:
            raise
        else:
            self.control_board = DmfControlBoard()

        self.port = self.get_port()

        if not self.control_board.connected():
            del self.control_board
            raise ConnectionError('Could not connect to device.')
        else:
            self.firmware_version = self.control_board.software_version()
            self.driver_version = self.control_board.host_software_version()
            del self.control_board


    def test_connection(self, port):
        from hardware.dmf_control_board.device import DmfControlBoard

        try:
            if self.control_board.connect(port) == DmfControlBoard.RETURN_OK:
                self.port = port
                self.control_board.flush()
                name = self.control_board.name()
                version = 0
                if is_float(self.control_board.hardware_version()):
                    version = float(self.control_board.hardware_version())
                if name == "Arduino DMF Controller" and version >= 1.1:
                    return True
        except:
            pass
        return False
