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
import tempfile
import tarfile
import os
import time
import re
import warnings

from hardware.avr import AvrDude, FirmwareError
from hardware.serial_device import SerialDevice
from hardware import hardware_path
from utility import is_float
from utility import path


class FirmwareUpdater(object):
    def __init__(self, module_name, hex_name, library_name):
        self.module_path = hardware_path() / path(module_name)
        self.FILE_PATTERNS = [
            dict(pattern=r'.*\.dll', destination=self.module_path),
        ]
        self.hex_name = hex_name
        self.library_name = library_name
        self.tar = None
        self.temp_dir = None
        self.bin_dir = None
        self.firmware = None
        self.driver = None
        self.version = None
        self.avrdude = AvrDude()

    def update(self, firmware_version=None, driver_version=None):
        update_path = self.module_path / path('update')

        # Look for update tar file
        files = sorted(update_path.files('*.tar.gz'), key=lambda x: x.name)
        if not files:
            # No update archive - nothing to do.
            warnings.warn("No update archive.")
            return

        update_file = files[-1]
        print "checking %s for update" % update_file
        updated = False
        
        try:
            self.tar = tarfile.open(update_file)
            self.temp_dir = path(tempfile.mkdtemp())
            print 'created temp dir: %s' % self.temp_dir

            # Extract update archive to temporary directory
            self.tar.extractall(self.temp_dir)
            
            bin_dirs = [d for d in self.temp_dir.walkdirs() if d.name == 'bin']
            if not bin_dirs:
                raise FirmwareError('bin directory does not exist in archive.')
            
            self.bin_dir = bin_dirs[0]
            
            self._verify_archive()
            if firmware_version < self.version:
                # Flash new firmware
                print '''Firmware needs to be updated: "%s" < "%s" '''\
                    % (firmware_version, self.version)
                self._update_firmware()
                updated = True
            else:
                print '''Firmware is up-to-date: "%s" >= "%s" '''\
                    % (firmware_version, self.version)
            if driver_version < self.version:
                print '''Driver needs to be updated: "%s" < "%s" '''\
                    % (driver_version, self.version)
                self.driver.copy(self.module_path / self.driver.name)
                updated = True
            else:
                print '''Driver is up-to-date: "%s" >= "%s" '''\
                    % (driver_version, self.version)
            for f in self.bin_dir.walkfiles():
                for p in self.FILE_PATTERNS:
                    if re.match(p['pattern'], f.name):
                        dest_path = path(p['destination']) / f.name
                        if not dest_path.isfile() \
                            or f.mtime > dest_path.mtime \
                            or not f.size == dest_path.size:
                            print 'copying %s to %s' % (f, dest_path)
                            f.copy(dest_path)
                            updated = True
                        break
        finally:
            self.clean_up()
        return updated

    def _verify_archive(self):
        firmware = self.bin_dir / path(self.hex_name + '.hex')
        if os.name == 'nt':
            driver = self.bin_dir / path(self.library_name + '.pyd')
        else:
            driver = self.bin_dir / path(self.library_name + '.so')
        version = self.bin_dir / path('version.txt')
        if not firmware.isfile():
            raise FirmwareError('%s does not exist in archive' % firmware)
        if not driver.isfile():
            raise FirmwareError('%s does not exist in archive' % driver)
        if not version.isfile():
            raise FirmwareError('%s does not exist in archive' % version)
        self.version = version.bytes().strip()
        self.firmware = firmware
        self.driver = driver

    def clean_up(self):
        if self.tar:
            self.tar.close()
        if self.temp_dir:
            self.temp_dir.rmtree()

    def _update_firmware(self):
        stdout, stderr = self.avrdude.flash(self.firmware.abspath())
        if stdout:
            print stdout
        if stderr:
            print stderr
        return True