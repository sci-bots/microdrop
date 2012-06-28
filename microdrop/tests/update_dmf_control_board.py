import os
import subprocess

if __name__ == '__main__':
    os.chdir('microdrop/plugins')
    
    if not os.path.exists('dmf_control_board'):
        print 'Clone dmf_control_board repository...'
        subprocess.check_call(['git', 'clone',
            'http://microfluidics.utoronto.ca/git/dmf_control_board.git'])
    else:
        print 'Fetch lastest update...'
        subprocess.check_call(['git', 'pull'])