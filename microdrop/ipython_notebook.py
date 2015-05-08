# coding: utf-8
import pkg_resources
from subprocess import Popen
import sys

from path_helpers import path


class IPythonNotebookSession(object):
    def __init__(self, daemon=False, **kwargs):
        self.daemon = daemon
        self.kwargs = kwargs
        self.process = None

    @property
    def args(self):
        args = ()
        for k, v in self.kwargs.iteritems():
            cli_k = k.replace('_', '-')
            if v is not None:
                args += ('--%s=%s' % (cli_k, v), )
        return args

    def start(self, *args, **kwargs):
        args_ = ('%s' % sys.executable, '-m', 'IPython', 'notebook') + self.args
        args_ = args_ + tuple(args)
        self.process = Popen(args_, **kwargs)

    def __del__(self):
        if self.daemon and self.process is not None:
            self.process.kill()
