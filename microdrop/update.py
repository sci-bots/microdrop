"""
Copyright 2011 Ryan Fobel and Christian Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import subprocess
import warnings


def firmware_needs_update():
    return subprocess.call([sys.executable, __file__])

def extension_needs_update():
    pass

if __name__ == '__main__':
    
    from hardware.avr import FirmwareUpdater, FirmwareError
    from hardware.dmf_control_board import DmfControlBoardInfo, ConnectionError

    force_update = False
    try:
        d = DmfControlBoardInfo()
    except (ConnectionError, ImportError):
        # Could not import DmfControlBoard, force update
        force_update = True
    
    updated = False
    try:
        f = FirmwareUpdater("dmf_control_board", "dmf_driver", "dmf_control_board_base")
        print 'forcing update:', force_update
        if force_update:
            updated = f.update()
        else:
            updated = f.update(
                        firmware_version=d.firmware_version,
                        driver_version=d.driver_version)
    except ConnectionError, why:
        warnings.warn(str(why))
    exit(force_update)