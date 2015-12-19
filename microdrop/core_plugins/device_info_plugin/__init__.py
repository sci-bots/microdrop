"""
Copyright 2015 Christian Fobel

This file is part of device_info_plugin.

device_info_plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with device_info_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""
from path_helpers import path
from flatland import Form, String
from microdrop.plugin_helpers import AppDataController, get_plugin_info
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements)
from microdrop.app import get_app

from zmq_plugin.plugin import Plugin as ZmqPlugin


class DeviceInfoZmqPlugin(ZmqPlugin):
    def on_execute__get_device(self):
        app = get_app()
        controller = app.dmf_device_controller
        device = controller.dmf_device
        return device


PluginGlobals.push_env('microdrop.managed')


class DeviceInfoPlugin(Plugin, AppDataController):
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

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
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
        super(DeviceInfoPlugin, self).on_plugin_enable()
        app_values = self.get_app_values()
        self.plugin = DeviceInfoZmqPlugin(self.name, app_values['hub_uri'])
        # Initialize sockets.
        self.plugin.reset()

    def cleanup(self):
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
