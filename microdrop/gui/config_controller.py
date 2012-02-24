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

import gtk

from dmf_device import DmfDevice
from protocol import Protocol
from plugin_manager import IPlugin, SingletonPlugin, implements, \
    emit_signal, PluginGlobals
from app_context import get_app


PluginGlobals.push_env('microdrop')


class ConfigController(SingletonPlugin):
    implements(IPlugin)
        
    def __init__(self):
        self.name = "microdrop.gui.config_controller"

    def on_app_init(self):
        self.app = get_app()
        self.app.config_controller = self

    def on_app_exit(self):
        self.app.config.save()
        
    def process_config_file(self):
        # save the protocol name from the config file because it is
        # automatically overwritten when we load a new device
        protocol_name = self.app.config['protocol']['name']
        self.load_dmf_device()
        # reapply the protocol name to the config file
        self.app.config['protocol']['name'] = protocol_name
        self.load_protocol()
    
    def load_dmf_device(self):
        # try what's specified in config file
        if self.app.config['dmf_device']['name'] != None:
            path = os.path.join(self.app.config['dmf_device']['directory'],
                                self.app.config['dmf_device']['name'],
                                "device")
            self.app.dmf_device_controller.load_device(path)

    def load_protocol(self):
        if self.app.config['dmf_device']['name']:
            # try what's specified in config file
            if self.app.config['protocol']['name'] != None:
                filename = os.path.join(self.app.config['dmf_device']['directory'],
                                        self.app.config['dmf_device']['name'],
                                        "protocols",
                                        self.app.config['protocol']['name'])
                self.app.protocol_controller.load_protocol(filename)
                
    def on_dmf_device_changed(self, dmf_device):
        self.app.config['dmf_device']['name'] = dmf_device.name
        
    def on_protocol_changed(self, protocol):
        self.app.config['protocol']['name'] = protocol.name


PluginGlobals.pop_env()
