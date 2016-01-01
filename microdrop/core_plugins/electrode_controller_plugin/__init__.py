"""
Copyright 2015 Christian Fobel

This file is part of electrode_controller_plugin.

electrode_controller_plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with electrode_controller_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""
import cPickle as pickle

from flatland import Form, String
from microdrop.app_context import get_app
from microdrop.plugin_helpers import AppDataController, get_plugin_info
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements, ScheduleRequest)
from path_helpers import path
from zmq_plugin.plugin import Plugin as ZmqPlugin
import gobject
import zmq


class DeviceInfoZmqPlugin(ZmqPlugin):
    def on_execute__get_device(self, request):
        app = get_app()
        return app.dmf_device

    def on_execute__get_svg_frame(self, request):
        app = get_app()
        return app.dmf_device.get_svg_frame()

    def on_execute__get_electrode_channels(self, request):
        app = get_app()
        return app.dmf_device.get_electrode_channels()

    def on_execute__dumps(self, request):
        app = get_app()
        return pickle.dumps(app.dmf_device)


PluginGlobals.push_env('microdrop.managed')


class ElectrodeControllerPlugin(Plugin, AppDataController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    version = get_plugin_info(path(__file__).parent).version
    plugin_name = get_plugin_info(path(__file__).parent).plugin_name

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
        String.named('hub_uri').using(optional=True,
                                      default='tcp://localhost:31000'),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.command_timeout_id = None

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('wheelerlab.zmq_hub_plugin', self.name)]
        else:
            return []

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
        super(ElectrodeControllerPlugin, self).on_plugin_enable()
        app_values = self.get_app_values()

        self.cleanup()
        self.plugin = DeviceInfoZmqPlugin(self.name, app_values['hub_uri'])
        # Initialize sockets.
        self.plugin.reset()

        def check_command_socket():
            try:
                msg_frames = (self.plugin.command_socket
                              .recv_multipart(zmq.NOBLOCK))
            except zmq.Again:
                pass
            else:
                self.plugin.on_command_recv(msg_frames)
            return True

        self.command_timeout_id = gobject.timeout_add(10, check_command_socket)

    def cleanup(self):
        if self.command_timeout_id is not None:
            gobject.source_remove(self.command_timeout_id)
        if self.plugin is not None:
            self.plugin = None

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        self.cleanup()

    def on_app_exit(self):
        """
        Handler called just before the Microdrop application exits.
        """
        self.cleanup()


PluginGlobals.pop_env()
