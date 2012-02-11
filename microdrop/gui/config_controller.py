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
import shutil

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
        # TODO: prompt to save if these have been changed 
        self.save_dmf_device()
        self.save_protocol()
        self.app.config.save()
        
    def process_config_file(self):
        # save the protocol name from the config file because it is
        # automatically overwritten when we load a new device
        protocol_name = self.app.config['protocol']['name']
        self.load_dmf_device()
        # reapply the protocol name to the config file
        self.app.config['protocol']['name'] = protocol_name
        self.load_protocol()

    def dmf_device_name_dialog(self, name=None):
        if name is None:
            name=""
        return self.app.main_window_controller.get_text_input("Save device",
                                                              "Device name",
                                                              name)
    
    def protocol_name_dialog(self, name=None):
        if name is None:
            name=""
        return self.app.main_window_controller.get_text_input("Save protocol",
                                                              "Protocol name",
                                                              name)

    def save_dmf_device(self, save_as=False, rename=False):
        # if the device has no name, try to get one
        if save_as or rename or self.app.dmf_device.name is None:
            # if the dialog is canceled, name = ""
            name = self.dmf_device_name_dialog(self.app.dmf_device.name)
        else:
            name = self.app.dmf_device.name

        if name:
            # current file name
            if self.app.dmf_device.name:
                src = os.path.join(self.app.config['dmf_device']['directory'],
                                   self.app.dmf_device.name)
            dest = os.path.join(self.app.config['dmf_device']['directory'],name)

            # if we're renaming, move the old directory
            if rename and os.path.isdir(src):
                if src == dest:
                    return
                if os.path.isdir(dest):
                    self.app.main_window_controller.error("A device with that "
                        "name already exists.")
                    return
                shutil.move(src, dest)

            if os.path.isdir(dest) == False:
                os.mkdir(dest)

            # save the device            
            self.app.dmf_device.name = name
            self.app.dmf_device.save(os.path.join(dest,"device"))
            
            # update config
            self.app.config['dmf_device']['name'] = name
            self.app.main_window_controller.update()
        
    def save_protocol(self, save_as=False, rename=False):
        if self.app.dmf_device.name:
            if save_as or rename or self.app.protocol.name is None:
                # if the dialog is canceled, name = ""
                name = self.protocol_name_dialog(self.app.protocol.name)
            else:
                name = self.app.protocol.name

            if name:
                path = os.path.join(self.app.config['dmf_device']['directory'],
                                    self.app.dmf_device.name,
                                    "protocols")
                if os.path.isdir(path) == False:
                    os.mkdir(path)

                # current file name
                if self.app.protocol.name:
                    src = os.path.join(path, self.app.protocol.name)
                dest = os.path.join(path,name)
                self.app.protocol.name = name

                # if we're renaming
                if rename and os.path.isfile(src):
                    shutil.move(src, dest)
                else: # save the file
                    self.app.protocol.save(dest)
    
                # update config
                self.app.config['protocol']['name'] = name
                self.app.main_window_controller.update()
    
    def load_dmf_device(self):
        dmf_device = None

        # try what's specified in config file
        if self.app.config['dmf_device']['name'] != None:
            path = os.path.join(self.app.config['dmf_device']['directory'],
                                self.app.config['dmf_device']['name'],
                                "device")
            try:
                dmf_device = DmfDevice.load(path)
            except:
                self.app.main_window_controller.error("Could not open %s" % path)

        # otherwise, return a new object
        if dmf_device==None:
            dmf_device = DmfDevice()
        emit_signal("on_dmf_device_changed", dmf_device)

    def load_protocol(self):
        if self.app.config['dmf_device']['name']:
            # try what's specified in config file
            if self.app.config['protocol']['name'] != None:
                filename = os.path.join(self.app.config['dmf_device']['directory'],
                                        self.app.config['dmf_device']['name'],
                                        "protocols",
                                        self.app.config['protocol']['name'])
                self.app.protocol_controller.load_protocol(filename)
            # otherwise, return a new object
            else:
                protocol = Protocol(self.app.dmf_device.max_channel()+1)
                emit_signal("on_protocol_changed", protocol)
                
    def on_dmf_device_changed(self, dmf_device):
        self.app.config['dmf_device']['name'] = dmf_device.name
        
    def on_protocol_changed(self, protocol):
        self.app.config['protocol']['name'] = protocol.name


PluginGlobals.pop_env()
