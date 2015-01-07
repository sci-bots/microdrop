"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import os

from path_helpers import path
from microdrop_utility.user_paths import home_dir

from ..logger import logger
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ExtensionPoint, ScheduleRequest)
from ..app_context import get_app


PluginGlobals.push_env('microdrop')


class ConfigController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.config_controller"
        self.app = None

    def on_plugin_enable(self):
        self.app = get_app()
        self.app.config_controller = self

        # load all app options from the config file
        observers = ExtensionPoint(IPlugin)
        for section_name, values_dict in self.app.config.data.iteritems():
            service = observers.service(section_name)
            if service:
                if hasattr(service, 'set_app_values'):
                    service.set_app_values(values_dict)
                else:
                    logger.error('Invalid section in config file: [%s].' %
                                 section_name)
                    self.app.config.data.pop(section_name)

    def on_app_exit(self):
        self.app.config.save()

    def on_dmf_device_changed(self):
        device_name = None
        if self.app.dmf_device:
            device_name = self.app.dmf_device.name
        if self.app.config['dmf_device']['name'] != device_name:
            self.app.config['dmf_device']['name'] = device_name
            self.app.config.save()

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        self.on_dmf_device_changed()

    def on_protocol_changed(self):
        if self.app.protocol.name != self.app.config['protocol']['name']:
            self.app.config['protocol']['name'] = self.app.protocol.name
            self.app.config.save()

    def on_protocol_swapped(self, old_protocol, protocol):
        self.on_protocol_changed()

    def on_app_options_changed(self, plugin_name):
        if self.app is None:
            return
        logger.debug('[ConfigController] on_app_options_changed: %s' %
                     plugin_name)
        observers = ExtensionPoint(IPlugin)
        service = observers.service(plugin_name)
        if service:
            if not hasattr(service, 'get_app_values'):
                return
            app_options = service.get_app_values()
            if app_options:
                if not plugin_name in self.app.config.data:
                    self.app.config.data[plugin_name] = {}
                self.app.config.data[plugin_name].update(app_options)
                self.app.config.save()

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest("microdrop.gui.main_window_controller",
                                    self.name)]
        elif function_name == 'on_protocol_swapped':
            # make sure that the app's protocol reference is valid
            return [ScheduleRequest("microdrop.app",
                                    self.name)]
        elif function_name == 'on_dmf_device_swapped':
            # make sure that the app's dmf device reference is valid
            return [ScheduleRequest("microdrop.app",
                                    self.name)]
        return []


PluginGlobals.pop_env()
