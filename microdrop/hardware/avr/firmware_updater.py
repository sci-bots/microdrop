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

import sys
import os
import time
import re
import warnings

from hardware.avr import AvrDude, FirmwareError
from hardware.serial_device import SerialDevice
from hardware import hardware_path
from utility import is_float
from utility import path
from update import Updater


class FirmwareUpdater(Updater):
    def __init__(self, module_path, hex_name):
        Updater.__init__(self, module_path)
        self.avrdude = AvrDude()
        self.firmware = self.bin_dir / path(hex_name)

    def update(self):
        stdout, stderr = self.avrdude.flash(self.firmware)
        if stdout:
            print stdout
        if stderr:
            print stderr
        return True