import os
import sys
import subprocess

if __name__ == '__main__':
    os.chdir('microdrop/plugins')
    try:
        if not os.path.exists('dmf_control_board'):
            print 'Clone dmf_control_board repository...'
            print subprocess.check_output(['git', 'clone',
                'http://microfluidics.utoronto.ca/git/dmf_control_board.git'],
                stderr=subprocess.STDOUT)
        else:
            print 'Fetch lastest dmf_control_board update...'
            print subprocess.check_output(['git', 'pull'],
                                          stderr=subprocess.STDOUT)
        sys.exit(0)
    except subprocess.CalledProcessError, e:
        print e.output
        sys.exit(e.returncode)