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

import getopt
import sys
import subprocess
import warnings
import tempfile
import tarfile
import os
import re

from utility import path, base_path

verbose = False

def archive_version():
    """Get the version string for the most recent archive file.  If no archive
    files can be found, this function will return an empty string.
    """
    version = subprocess.Popen([sys.executable, __file__, '--archive-version'],
                          stdout=subprocess.PIPE).communicate()[0].rstrip()
    return version

def firmware_version():
    """Get the version string of the firmware currently installed on the
    Arduino. If no Arduino is connected, or if the connected Arduino does not
    have the DmfControlBoard firmware installed, this function will return an
    empty string.
    """
    version = subprocess.Popen([sys.executable, __file__, '--firmware-version'],
                          stdout=subprocess.PIPE).communicate()[0].rstrip()
    return version


def package_version():
    """Get the version string of the currently installed DmfControlBoard
    package.
    """
    version = subprocess.Popen([sys.executable, __file__, '--package-version'],
                          stdout=subprocess.PIPE).communicate()[0].rstrip()
    return version


def update_firmware():
    """Update the Arduino with firmware from the most recent archive.
    Returns True if successful, False otherwise.
    """
    p = subprocess.Popen([sys.executable, __file__, '--update-firmware'],
                         stdout=subprocess.PIPE)
    output = p.communicate()[0].rstrip()
    if output and verbose:
        print output
    return p.returncode==0


def update_package():
    """Update the DmfControlBoard package using the most recent archive.
    Returns True if successful, False otherwise.
    """
    p = subprocess.Popen([sys.executable, __file__, '--update-package'],
                         stdout=subprocess.PIPE)
    output = p.communicate()[0].rstrip()
    if output and verbose:
        print output
    return p.returncode==0


def usage():
    print("""Usage: update [options]
    --archive-version      Get the version of the archive
    --firmware-version     Get the firmware version
    --package-version      Get the package version
    --update-firmware      Update the firmware
    --update-package       Update the package
    -v, --verbose          Print debug messages
""")


def main():
    """This funciton is called when the update module is called as a script.
    It can perform various actions (querying the DmfControlBoard firmware,
    package, or archive version number, or updating the firmware or package
    from the archive file). The action is specified by a command line argument.
    
    To see the available options run the following in a command terminal:
    >> update.py --help 
    """
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], ":hv",
            ["help", "archive-version", "firmware-version",
             "package-version", "update-firmware", "update-package"])
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    
    if len(opts)==0:
        usage()
        sys.exit(0)

    for o, a in opts:
        if o in ("-v", "--verbose"):
            print "verbose=True"
            opts.remove((o,a))
            global verbose
            verbose = True

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("--firmware-version"):
            from hardware.dmf_control_board import DmfControlBoardInfo, ConnectionError
            try:
                d = DmfControlBoardInfo()
                print d.firmware_version
            except (ImportError, ConnectionError):
                print ""
            exit(0)
        elif o in ("--package-version"):
            from hardware.dmf_control_board import DmfControlBoard, ConnectionError
            try:
                d = DmfControlBoard()
                print d.host_software_version()
            except:
                print ""
            exit(0)
        elif o in ("--archive-version"):
            try:
                u = Updater(base_path() / path("hardware") / path("dmf_control_board"))
                print u.version
                exit(0)
            except ArchiveError, why:
                warnings.warn(str(why))
                exit(1)
        elif o in ("--update-firmware"):
            try:
                from hardware.dmf_control_board.avr import AvrDude
                hex_path = base_path() / path("hardware") \
                           / path("dmf_control_board") / path("dmf_driver.hex")
                avrdude = AvrDude()
                stdout, stderr = avrdude.flash(hex_path)
                if stdout:
                    print stdout
                if stderr:
                    print stderr
            except Exception, why:
                print why
                exit(1)
        elif o in ("--update-package"):
            try:
                if os.name == 'nt':
                    file_names = ["\.pyd$", "\.dll$",
                                  "dmf_driver.hex",
                                  "version.txt"]
                else:
                    file_names = ["*.so", "dmf_driver.hex",
                                  "version.txt"]
                u = Updater(base_path() / path("hardware/dmf_control_board"))
                u.update(file_names)
                exit(0)
            except Exception, why:
                print why
                exit(1)
        else:
            assert False, "unhandled option"


class ArchiveError(Exception):
    pass


class Updater(object):
    """Class for handling component upgrades from an archive file."""
    def __init__(self, module_path):
        self.module_path = module_path
        self.tar = None
        self.temp_dir = None
        self.bin_dir = None
        self.version = None
        self._verify_archive()

    def __del__(self):
        if self.tar:
            if verbose:
                print "closing archive"
            self.tar.close()
        if self.temp_dir:
            if verbose:
                print "cleaning up temp directory:", self.temp_dir
            self.temp_dir.rmtree()

    def update(self, file_names):
        for f in self.bin_dir.walkfiles():
            for p in file_names:
                if re.search(p, f.name):
                    dest_path = path(self.module_path) / f.name
                    print 'copying %s to %s' % (f, dest_path)
                    f.copy(dest_path)
                    break

    def _verify_archive(self):
        update_path = self.module_path / path('update')

        # Look for update tar file
        files = sorted(update_path.files('*.tar.gz'), key=lambda x: x.name)
        if not files:
            # No update archive - nothing to do.
            warnings.warn("No update archive.")
            return

        update_file = files[-1]
        if verbose:
            print "checking %s for update" % update_file
        
        self.tar = tarfile.open(update_file)
        self.temp_dir = path(tempfile.mkdtemp())
        if verbose:
            print 'created temp dir: %s' % self.temp_dir

        # Extract update archive to temporary directory
        self.tar.extractall(self.temp_dir)
        
        bin_dirs = [d for d in self.temp_dir.walkdirs() if d.name == 'bin']
        if not bin_dirs:
            raise ArchiveError('bin directory does not exist in archive.')

        self.bin_dir = bin_dirs[0]

        version = self.bin_dir / path('version.txt')
        if not version.isfile():
            raise ArchiveError('%s does not exist in archive' % version)
        self.version = version.bytes().strip()


if __name__ == '__main__':
    main()