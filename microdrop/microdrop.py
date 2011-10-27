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

import update

if __name__ == '__main__':
    archive_version = update.archive_version()
    firmware_version = update.firmware_version()
    driver_version = update.package_version()

    print "archive version=", archive_version
    print "firmware_version=", firmware_version
    print "driver_version=", driver_version

    if driver_version != archive_version:
        print "updating driver..."
        if update.update_package():
            print "   success"
        else:
            print "   failed"
    
    if firmware_version != archive_version:
        print "updating firmware..."
        if update.update_firmware():
            print "   success"
        else:
            print "   failed"
        
    from app import App
    app = App()