"""
Copyright 2011 Ryan Fobel

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

import os
import warnings

from utility import script_dir



if __name__ == '__main__':
    import sys
    from hardware.update.dmf_control_board.firmware_updater import \
            FirmwareUpdater, FirmwareError, DmfControlBoardInfo, ConnectionError

    os.chdir(script_dir())

    force_update = False
    try:
        d = DmfControlBoardInfo()
    except (ConnectionError, ImportError):
        # Could not import DmfControlBoard, force update
        force_update = True

    updated = False
    try:
        f = FirmwareUpdater(hw_path='hardware')
        print force_update
        if force_update:
            print 'forcing update'
            updated = f.update()
        else:
            print 'forcing update'
            updated = f.update(
                        firmware_version=d.firmware_version,
                        driver_version=d.driver_version)
    except ConnectionError, why:
        warnings.warn(str(why))

    if updated:
        from gui.standalone_message_dialog import MessageDialog
           
        m = MessageDialog()
        m.info('Driver/firmware was updated - must restart application.')
    else:
        from microdrop_app import App

        app = App()
