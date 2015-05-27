# coding: utf-8
import webbrowser
from subprocess import Popen, PIPE
import sys
import os
import re

from path_helpers import path


class IPythonNotebookSession(object):
    def __init__(self, daemon=False, **kwargs):
        self.daemon = daemon
        self.kwargs = kwargs
        self.process = None
        self.stderr_lines = []
        self.port = None
        self.address = None
        self._notebook_dir = None

    @property
    def args(self):
        args = ()
        for k, v in self.kwargs.iteritems():
            cli_k = k.replace('_', '-')
            if v is not None:
                args += ('--%s=%s' % (cli_k, v), )
        return args

    def start(self, *args, **kwargs):
        if 'stderr' in kwargs:
            raise ValueError('`stderr` must not be specified, since it must be'
                             ' monitored to determine which port the notebook '
                             'server is running on.')
        args_ = ('%s' % sys.executable, '-m', 'IPython', 'notebook') + self.args
        args_ = args_ + tuple(args)
        self.process = Popen(args_, stderr=PIPE, **kwargs)
        self._notebook_dir = os.getcwd()

        # Determine which port the notebook is running on.
        cre_address = re.compile(r'The IPython Notebook is running at: '
                                 r'(?P<address>https?://.*?:'
                                 r'(?P<port>\d+).*/)$')
        cre_notebook_dir = re.compile(r'Serving notebooks from local '
                                      r'directory:\s+(?P<notebook_dir>.*)$')
        match = None
        self.stderr_lines = []

        while not self.process.poll() and match is None:
            stderr_line = self.process.stderr.readline()
            self.stderr_lines.append(stderr_line)
            match = cre_address.search(stderr_line)
            dir_match = cre_notebook_dir.search(stderr_line)
            if dir_match:
                self._notebook_dir = dir_match.group('notebook_dir')

        if match:
            # Notebook was started successfully.
            self.address = match.group('address')
            self.port = int(match.group('port'))
        else:
            raise IOError(''.join(self.stderr_lines))

    @property
    def notebook_dir(self):
        if self._notebook_dir is None:
            raise ValueError('Notebook directory not.  Is the notebook server '
                             'running?')
        return path(self._notebook_dir)

    def resource_filename(self, filename):
        return self.notebook_dir.joinpath(filename)

    def open(self, filename):
        notebook_path = self.resource_filename(filename)
        if not notebook_path.isfile():
            raise IOError('Notebook path not found: %s' % notebook_path)
        else:
            webbrowser.open_new_tab('%snotebooks/%s' % (self.address,
                                                        filename))

    def stop(self):
        if self.daemon and self.process is not None:
            self.process.kill()

    def __del__(self):
        self.stop()
