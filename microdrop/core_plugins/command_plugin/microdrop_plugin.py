import logging

from logging_helpers import _L
from pygtkhelpers.gthreads import gtk_threadsafe
import threading
import zmq

from .plugin import CommandZmqPlugin
from ...app_context import get_hub_uri
from ...plugin_helpers import hub_execute
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements)

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop')


class CommandPlugin(SingletonPlugin):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    plugin_name = 'microdrop.command_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.stopped = threading.Event()

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.

        Note: if you inherit your plugin from AppDataController and don't
        implement this handler, by default, it will automatically load all
        app options from the config file. If you decide to overide the
        default handler, you should call:

            AppDataController.on_plugin_enable(self)

        to retain this functionality.

        .. versionchanged:: 2.11.2
            Launch background thread to monitor plugin ZeroMQ command socket.

            Use :func:`gtk_threadsafe` decorator to wrap thread-related code
            to ensure GTK/GDK are initialized properly for a threaded
            application.
        """
        self.cleanup()

        zmq_ready = threading.Event()

        def _check_command_socket(wait_duration_s):
            '''
            Process each incoming message on the ZeroMQ plugin command socket.

            Stop listening if :attr:`stopped` event is set.
            '''
            self.stopped.clear()
            self.plugin = CommandZmqPlugin(self, self.name, get_hub_uri())
            # Initialize sockets.
            self.plugin.reset()
            zmq_ready.set()
            while not self.stopped.wait(wait_duration_s):
                try:
                    msg_frames = (self.plugin.command_socket
                                  .recv_multipart(zmq.NOBLOCK))
                except zmq.Again:
                    pass
                else:
                    self.plugin.on_command_recv(msg_frames)

        thread = threading.Thread(target=_check_command_socket,
                                    args=(0.01, ))
        thread.daemon = True
        thread.start()
        zmq_ready.wait()

    def cleanup(self):
        self.stopped.set()
        if self.plugin is not None:
            self.plugin = None

    def on_plugin_enabled(self, *args, **kwargs):
        # A plugin was enabled.  Call `get_commands()` on self to trigger
        # refresh of commands in case the enabled plugin registered a command.
        hub_execute(self.name, 'get_commands')
        _L().info('refreshed registered commands.')

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        self.cleanup()

    def on_app_exit(self):
        """
        Handler called just before the MicroDrop application exits.
        """
        self.cleanup()


PluginGlobals.pop_env()
