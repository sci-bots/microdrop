from subprocess import Popen, PIPE
import sys
import tempfile
import tarfile
import os
import time

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


class FirmwareError(Exception):
    pass


class FirmwareUpdater(object):
    def __init__(self, hw_path=None):
        if hw_path is None:
            self.hw_path = self.get_hardware_path()
        else:
            self.hw_path = path(hw_path)
        self.tar = None
        self.temp_dir = None
        self.firmware = None
        self.driver = None
        self.version = None
        if os.name == 'nt':
            self.avrdude = self.hw_path / path('avr') / path('avrdude.exe')
        else:
            self.avrdude = self.hw_path / ppath('avr') / ath('avrdude')
        if not self.avrdude.exists():
            raise FirmwareError('avrdude not installed')


    def get_hardware_path(self):
        test_dir = path(os.getcwd())
        while test_dir and not (test_dir / path('hardware')).isdir():
            test_dir = test_dir.parent
        if not test_dir:
            raise FirmwareError('''Could not find 'hardware' directory''')
        return test_dir / path('hardware')


    def update(self, port):
        update_path = self.hw_path / path('update/dmf_control_board')

        # Look for update tar file
        files = update_path.files('*.tgz')
        if not files:
            pass
        elif len(files) > 1:
            raise FirmwareError('''Multiple .tgz files found in %s.'''\
                                    % update_path)
        update_file = files[0]
        
        try:
            self.tar = tarfile.open(update_file)
            self.temp_dir = path(tempfile.mkdtemp(prefix='dmf_control_board'))
            print 'created temp dir: %s' % self.temp_dir

            # Extract update archive to temporary directory
            self.tar.extractall(self.temp_dir)
            print list(self.temp_dir.walkfiles())
            self._verify_archive()
            self._update_firmware(port)
            self.driver.copy(self.hw_path / self.driver.name)
        finally:
            self.clean_up()
    

    def _verify_archive(self):
        firmware = self.temp_dir / path('bin') / path('dmf_driver.hex')
        if os.name == 'nt':
            driver = self.temp_dir / path('bin') / path('dmf_control_board_base.pyd')
        else:
            driver = self.temp_dir / path('bin') / path('dmf_control_board_base.so')
        version = self.temp_dir / path('bin') / path('version.txt')
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
        from exceptions import WindowsError

        if self.tar:
            self.tar.close()
        if self.temp_dir:
            self.temp_dir.rmtree()


    def _update_firmware(self, port):
        config = dict(avrdude=self.avrdude.abspath(),
            avrconf=(self.hw_path / path('avr') / path('avrdude.conf')).abspath(),
            firmware=self.firmware.name, port=port)
        cwd = os.getcwd()
        os.chdir(self.temp_dir / path('bin'))
        cmd_fmt = '%(avrdude)s -V -F -c stk500v2 -b 115200 -p atmega2560 -P %(port)s -U flash:w:%(firmware)s -C %(avrconf)s'
        cmd = ['%(avrdude)s', '-V', '-F', '-c', 'stk500v2', '-b', '115200', '-p', 'atmega2560', '-P', '%(port)s', '-U', 'flash:w:%(firmware)s', '-C', '%(avrconf)s']
        cmd = [v % config for v in cmd]
        print cmd
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        os.chdir(cwd)
        if p.returncode:
            raise FirmwareError(stderr)
        print stdout
        print stderr
        return True


if __name__ == '__main__':
    f = FirmwareUpdater()
    f.update('COM3')
