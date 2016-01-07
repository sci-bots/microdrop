"""
Copyright 2015 Christian Fobel

This file is part of zmq_hub_plugin.

zmq_hub_plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with zmq_hub_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""
from multiprocessing import Process
import logging

from flatland import Form, String, Enum
from zmq_plugin.bin.hub import run_hub
from zmq_plugin.hub import Hub

from ...plugin_helpers import AppDataController
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements)

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop')


class MicrodropHub(Hub):
    def on_command_recv(self, msg_frames):
        try:
            super(MicrodropHub, self).on_command_recv(msg_frames)
        except:
            logger.error('Command socket message error.', exc_info=True)


class ZmqHubPlugin(SingletonPlugin, AppDataController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    plugin_name = 'wheelerlab.zmq_hub_plugin'

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
        .valued('debug', 'info', 'warning', 'error', 'critical'),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.hub_process = None

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.

        Note: if you inherit your plugin from AppDataController and don't
        implement this handler, by default, it will automatically load all
        app options from the config file. If you decide to overide the
        default handler, you should call:

            AppDataController.on_plugin_enable(self)

        to retain this functionality.
        """
        super(ZmqHubPlugin, self).on_plugin_enable()
        app_values = self.get_app_values()
        self.hub_process = Process(target=run_hub,
                                   args=(MicrodropHub(app_values['hub_uri'],
                                                      self.name),
                                         getattr(logging,
                                                 app_values['log_level']
                                                 .upper())))
        self.hub_process.start()

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        if self.hub_process is not None:
            self.hub_process.terminate()
            self.hub_process = None


PluginGlobals.pop_env()
