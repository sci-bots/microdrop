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
import utility

import update

if __name__ == '__main__':
    # Change directory to where microdrop.py resides, so this program can be
    # run from any directory.
    os.chdir(utility.base_path())

    """
    archive_version = update.archive_version()
    driver_version = update.package_version()
    firmware_version = update.firmware_version()

    print "archive version=", archive_version
    print "driver_version=", driver_version
    print "firmware_version=", firmware_version

    if driver_version != archive_version:
        print "updating driver to version %s..." % archive_version
        if update.update_package():
            print "   success"
        else:
            print "   failed"
    
    if firmware_version != archive_version:
        print "updating firmware to version %s..." % archive_version
        if update.update_firmware():
            print "   success"
        else:
            print "   failed"
    """
        
    from app import App
    app = App()
