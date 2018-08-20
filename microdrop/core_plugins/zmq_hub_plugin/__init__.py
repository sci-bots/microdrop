# coding: utf-8
from multiprocessing import Process
import logging
import signal
import threading

from asyncio_helpers import cancellable
from flatland import Form, String, Enum
from logging_helpers import _L
from zmq_plugin.bin.hub import run_hub
from zmq_plugin.hub import Hub
from zmq_plugin.plugin import Plugin as ZmqPlugin
import trollius as asyncio

from ...app_context import get_hub_uri
from ...plugin_helpers import AppDataController
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements)

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop')


def _safe_run_hub(*args, **kwargs):
    '''
    .. versionadded:: 2.15.2

    Wrap :func:`run_hub` to catch ``SIGINT`` signal (i.e., when `control-C` is
    pressed).
    '''
    signal.signal(signal.SIGINT, lambda *args: None)
    return run_hub(*args, **kwargs)


class MicroDropHub(Hub):
    def on_command_recv(self, msg_frames):
        try:
            super(MicroDropHub, self).on_command_recv(msg_frames)
        except Exception:
            _L().error('Command socket message error.', exc_info=True)


class ZmqHubPlugin(SingletonPlugin, AppDataController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    plugin_name = 'microdrop.zmq_hub_plugin'

    '''
    AppFields
    ---------

    A flatland Form specifying application options for the current plugin.
    Note that nested Form objects are not supported.

    Since we subclassed AppDataController, an API is available to access and
    modify these attributes.  This API also provides some nice features
    automatically:
        -all fields listed here will be included in the app options dialog
            (unless properties=dict(show_in_gui=False) is used)
        -the values of these fields will be stored persistently in the microdrop
            config file, in a section named after this plugin's name attribute
    '''
    AppFields = Form.of(
        String.named('hub_uri').using(optional=True, default='tcp://*:31000'),
        Enum.named('log_level').using(default='info', optional=True)
        .valued('debug', 'info', 'warning', 'error', 'critical'))

    def __init__(self):
        self.name = self.plugin_name
        self.hub_process = None
        #: ..versionadded:: 2.25
        self.exec_thread = None

    def on_plugin_enable(self):
        '''
        .. versionchanged:: 2.25
            Start asyncio event loop in background thread to process ZeroMQ hub
            execution requests.
        '''
        super(ZmqHubPlugin, self).on_plugin_enable()
        app_values = self.get_app_values()

        self.cleanup()
        self.hub_process = Process(target=_safe_run_hub,
                                   args=(MicroDropHub(app_values['hub_uri'],
                                                      self.name),
                                         getattr(logging,
                                                 app_values['log_level']
                                                 .upper())))
        # Set process as daemonic so it terminate when main process terminates.
        self.hub_process.daemon = True
        self.hub_process.start()
        _L().info('ZeroMQ hub process (pid=%s, daemon=%s)',
                  self.hub_process.pid, self.hub_process.daemon)

        zmq_ready = threading.Event()

        @asyncio.coroutine
        def _exec_task():
            self.zmq_plugin = ZmqPlugin('microdrop', get_hub_uri())
            self.zmq_plugin.reset()
            zmq_ready.set()

            event = asyncio.Event()
            try:
                yield asyncio.From(event.wait())
            except asyncio.CancelledError:
                _L().info('closing ZeroMQ execution event loop')

        self.zmq_exec_task = cancellable(_exec_task)
        self.exec_thread = threading.Thread(target=self.zmq_exec_task)
        self.exec_thread.deamon = True
        self.exec_thread.start()
        zmq_ready.wait()

    def cleanup(self):
        '''
        .. versionchanged:: 2.25
            Stop asyncio event loop.
        '''
        if self.hub_process is not None:
            self.hub_process.terminate()
            self.hub_process = None
        if self.exec_thread is not None:
            self.zmq_exec_task.cancel()
            self.exec_thread = None


PluginGlobals.pop_env()
