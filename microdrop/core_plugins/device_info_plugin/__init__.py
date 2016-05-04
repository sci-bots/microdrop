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
import cPickle as pickle

from zmq_plugin.plugin import Plugin as ZmqPlugin
import gobject
import zmq

from ...app_context import get_app, get_hub_uri
from ...plugin_manager import (PluginGlobals, ScheduleRequest, SingletonPlugin,
                               IPlugin, implements)


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


PluginGlobals.push_env('microdrop')


class DeviceInfoPlugin(SingletonPlugin):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    plugin_name = 'wheelerlab.device_info_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.command_timeout_id = None

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
        self.cleanup()
        self.plugin = DeviceInfoZmqPlugin(self.name, get_hub_uri())
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

    def on_dmf_device_swapped(self, old_device, new_device):
        if self.plugin is not None:
            # Notify other plugins that device has been swapped.
            self.plugin.execute_async(self.name, 'get_device')

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest instances)
        for the function specified by function_name.
        """
        if function_name == 'on_dmf_device_swapped':
            return [ScheduleRequest('microdrop.app', self.name)]
        return []


PluginGlobals.pop_env()
