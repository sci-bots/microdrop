from multiprocessing import Process
import logging
import sys

from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import pandas as pd

from logging_helpers import _L  #: .. versionadded:: 2.20


logger = logging.getLogger(__name__)


class CommandZmqPlugin(ZmqPlugin):
    '''
    API for registering commands.
    '''
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.control_board = None
        self._commands = pd.DataFrame(None, columns=['namespace',
                                                     'plugin_name',
                                                     'command_name', 'title'])
        super(CommandZmqPlugin, self).__init__(*args, **kwargs)

    def on_execute__unregister_command(self, request):
        data = decode_content_data(request)
        commands = self._commands
        ix = commands.loc[(commands.namespace == data['namespace']) &
                          (commands.plugin_name == data['plugin_name']) &
                          (commands.command_name == data['command_name']) &
                          (commands.title == data['title'])].index
        self._commands.drop(ix, inplace=True)
        self._commands.reset_index(drop=True, inplace=True)
        return self.commands

    def on_execute__register_command(self, request):
        data = decode_content_data(request)
        plugin_name = data.get('plugin_name', request['header']['source'])
        return self.register_command(plugin_name, data['command_name'],
                                     namespace=data.get('namespace', ''),
                                     title=data.get('title'))

    def on_execute__get_commands(self, request):
        return self.commands

    def register_command(self, plugin_name, command_name, namespace='',
                         title=None):
        '''
        Register command.

        Each command is unique by:

            (namespace, plugin_name, command_name)
        '''
        if title is None:
            title = (command_name[:1].upper() +
                     command_name[1:]).replace('_', ' ')
        row_i = dict(zip(self._commands, [namespace, plugin_name, command_name,
                                          title]))
        self._commands = self._commands.append(row_i, ignore_index=True)
        return self.commands

    @property
    def commands(self):
        '''
        Returns
        -------
        pd.Series
            Series of command groups, where each group name maps to a series of
            commands.
        '''
        return self._commands.copy()


def parse_args(args=None):
    """Parses arguments, returns (options, args)."""
    from argparse import ArgumentParser

    if args is None:
        args = sys.argv

    parser = ArgumentParser(description='ZeroMQ Plugin process.')
    log_levels = ('critical', 'error', 'warning', 'info', 'debug', 'notset')
    parser.add_argument('-l', '--log-level', type=str, choices=log_levels,
                        default='info')
    parser.add_argument('hub_uri')
    parser.add_argument('name', type=str)

    args = parser.parse_args()
    args.log_level = getattr(logging, args.log_level.upper())
    return args


if __name__ == '__main__':
    from zmq_plugin.bin.plugin import run_plugin

    def run_plugin_process(uri, name, subscribe_options, log_level):
        plugin_process = Process(target=run_plugin,
                                 args=())
        plugin_process.daemon = False
        plugin_process.start()

    args = parse_args()

    logging.basicConfig(level=args.log_level)
    task = CommandZmqPlugin(None, args.name, args.hub_uri, {})
    run_plugin(task, args.log_level)
