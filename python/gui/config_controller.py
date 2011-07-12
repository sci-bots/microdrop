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

import os, gtk

class ConfigController():
    def __init__(self, app):
        self.app = app
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                              "glade",
                              "new_dialog.glade"))
        self.new_dialog = builder.get_object("new_dialog")
        self.new_dialog.textentry = builder.get_object("textentry")
        self.new_dialog.label = builder.get_object("label")

    def dmf_device_name_dialog(self):
        self.new_dialog.set_title("Save device?")
        self.new_dialog.label.set_text("Device name:")
        self.new_dialog.textentry.set_text("")
        self.new_dialog.set_transient_for(self.app.main_window_controller.view)
        response = self.new_dialog.run()
        if response == gtk.RESPONSE_OK:
            self.app.dmf_device.name = self.new_dialog.textentry.get_text()
        self.new_dialog.hide()
        self.app.main_window_controller.update()
    
    def protocol_name_dialog(self):
        self.new_dialog.set_title("Save protocol?")
        self.new_dialog.label.set_text("Protocol name:")
        self.new_dialog.textentry.set_text("")
        self.new_dialog.set_transient_for(self.app.main_window_controller.view)
        response = self.new_dialog.run()
        if response == gtk.RESPONSE_OK:
            self.app.protocol.name = self.new_dialog.textentry.get_text()
        self.new_dialog.hide()
        self.app.main_window_controller.update()

    def save_dmf_device(self):
        # if the device has no name, try to get one
        if self.app.dmf_device.name is None:
            self.dmf_device_name_dialog()
        
        # update config
        self.app.config.dmf_device_name = self.app.dmf_device.name 

        if self.app.dmf_device.name:
            path = os.path.join(self.app.config.dmf_device_directory,
                                self.app.dmf_device.name)
            if os.path.isdir(path) == False:
                os.mkdir(path)
            self.app.dmf_device.save(os.path.join(path,"device"))

    def save_protocol(self):
        if self.app.dmf_device.name:
            # if the protocol has no name, try to get one
            if self.app.protocol.name is None:
                self.protocol_name_dialog()
            
            # update config
            self.app.config.protocol_name = self.app.protocol.name 
    
            if self.app.protocol.name:
                path = os.path.join(self.app.config.dmf_device_directory,
                                    self.app.dmf_device.name,
                                    "protocols")
                if os.path.isdir(path) == False:
                    os.mkdir(path)
                self.app.protocol.save(os.path.join(path,self.app.protocol.name))

    def on_quit(self):
        self.save_dmf_device()
        self.save_protocol()
        self.app.config.save()