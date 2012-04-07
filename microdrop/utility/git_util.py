import os
from subprocess import Popen, PIPE, check_call, CalledProcessError
import re

from path import path


class GitError(Exception):
    pass


class GitUtil(object):
    def __init__(self, root_path='.'):
        self.root_path = path(root_path)
        if root_path is None:
            dir_node = path(os.getcwd())
            while not dir_node.dirs('.git') and dir_node:
                dir_node = dir_node.parent
            if not dir_node:
                raise GitError('No git root found.')
            self.root_path = dir_node
        self._git = None
        assert(self.root_path.dirs('.git'))


    @property
    def git(self):
        if self._git:
            return self._git

        cmds = ['git']
        if os.name == 'nt':
            exceptions = (WindowsError,)
            cmds += ['git.cmd']
        else:
            exceptions = (OSError,)

        valid_cmd = False
        for cmd in cmds:
            try:
                check_call([cmd], stdout=PIPE, stderr=PIPE)
            except exceptions:
                # The command was not found, try the next one
                pass
            except CalledProcessError:
                valid_cmd = True
                break
        if not valid_cmd:
            raise GitError, 'No valid git command found'
        self._git = cmd
        return self._git


    def command(self, x):
        try:
            x.__iter__
        except:
            x = re.split(r'\s+', x)
        cwd = os.getcwd()

        os.chdir(self.root_path)
        cmd = [self.git] + x
        stdout, stderr = Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=PIPE).communicate()
        os.chdir(cwd)

        if stderr:
            raise GitError('Error executing git %s' % x)
        return stdout.strip()


    def describe(self):
        return self.command('describe')


    def summary(self, color=False):
        if color:
            format_ = '''--pretty=format:%Cred%h%Creset - %s %Cgreen(%cr)%Creset'''
        else:
            format_ = '''--pretty=format:%h - %s (%cr)'''
        return self.command(['''log''', '''--graph''', format_,
                    '''--abbrev-commit''', '''--date=relative'''])


    def rev_parse(self, ref='HEAD'):
        return self.command(['rev-parse', ref])


    def show(self, ref='HEAD', color=False, extra_args=None):
        extra_args = [extra_args, []][extra_args is None]
        args = ['show', ref]
        if color:
            args += ['--color']
        return self.command(args + extra_args)
