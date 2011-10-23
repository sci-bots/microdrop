from subprocess import Popen, PIPE, CalledProcessError
import sys
import tempfile
import tarfile
import os
import time
import re

from utility import is_float
from path import path


def script_dir():
    '''
    Return the path that this file resides in.

    NOTE: This function MUST stay in this file in order to return the proper
          path.  If moved, it will no longer return the path that THIS file
          resides in.
    '''
    try:
        script = path(__file__)
    except NameError:
        import sys

        script = path(sys.argv[0])
    return script.parent


class ConnectionError(Exception):
    pass


class FirmwareError(Exception):
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


class AvrDude(SerialDevice):
    def __init__(self, avrdude, avrconf):
        self.avrdude = path(avrdude)
        self.avrconf = path(avrconf)
        self.port = self.get_port()


    def _run_command(self, flags, verbose=False):
        config = dict(avrdude=self.avrdude, avrconf=self.avrconf)

        cmd = ['%(avrdude)s'] + flags
        cmd = [v % config for v in cmd]
        if verbose:
            print cmd
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


class DmfControlBoardInfo(SerialDevice):
    def __init__(self):
        self.port = None
        try:
            from hardware.dmf_control_board import DmfControlBoard
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
        from hardware.dmf_control_board import DmfControlBoard

        if self.control_board.connect(port) == DmfControlBoard.RETURN_OK:
            self.port = port
            self.control_board.flush()
            name = self.control_board.name()
            version = 0
            if is_float(self.control_board.hardware_version()):
                version = float(self.control_board.hardware_version())
            if name == "Arduino DMF Controller" and version >= 1.1:
                return True
        return False


class FirmwareUpdater(object):
    def __init__(self, hw_path=None):
        if hw_path is None:
            self.hw_path = self.get_hardware_path()
        else:
            self.hw_path = path(hw_path)

        self.FILE_PATTERNS = [
            dict(pattern=r'.*\.dll', destination=self.hw_path),
        ]

        self.tar = None
        self.temp_dir = None
        self.bin_dir = None
        self.firmware = None
        self.driver = None
        self.version = None
        if os.name == 'nt':
            self.avrdude_path = self.hw_path / path('avr') / path('avrdude.exe')
        else:
            self.avrdude_path = self.hw_path / path('avr') / path('avrdude')
        if not self.avrdude_path.exists():
            raise FirmwareError('avrdude not installed')
        self.avrdude = AvrDude(self.avrdude_path.abspath(),
            (self.hw_path / path('avr') / path('avrdude.conf')).abspath())
        print 'avrdude successfully connected on port: ', self.avrdude.port


    def get_hardware_path(self):
        test_dir = path(os.getcwd())
        while test_dir and not (test_dir / path('hardware')).isdir():
            test_dir = test_dir.parent
        if not test_dir:
            raise FirmwareError('''Could not find 'hardware' directory''')
        return test_dir / path('hardware')


    def update(self, firmware_version=None, driver_version=None):
        update_path = self.hw_path / path('update/dmf_control_board')

        # Look for update tar file
        files = sorted(update_path.files('*.tar.gz'), key=lambda x: x.name)
        if not files:
            # No update archive - nothing to do.
            return
        #elif len(files) > 1:
            #raise FirmwareError('''Multiple .tgz files found in %s.'''\
                                    #% update_path)
        update_file = files[-1]
        updated = False
        
        try:
            self.tar = tarfile.open(update_file)
            self.temp_dir = path(tempfile.mkdtemp(prefix='dmf_control_board'))
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
                print 'Firmware is up-to-date: %s' % firmware_version
            if driver_version < self.version:
                print '''Driver needs to be updated: "%s" < "%s" '''\
                    % (driver_version, self.version)
                self.driver.copy(self.hw_path / self.driver.name)
                print (self.hw_path / self.driver.name).size
                updated = True
            else:
                print 'Driver is up-to-date: %s' % driver_version
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
        firmware = self.bin_dir / path('dmf_driver.hex')
        if os.name == 'nt':
            driver = self.bin_dir / path('dmf_control_board_base.pyd')
        else:
            driver = self.bin_dir / path('dmf_control_board_base.so')
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


if __name__ == '__main__':
    f = FirmwareUpdater()
    f.update('COM3')
