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

import os, gtk, shutil

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

    def dmf_device_name_dialog(self, old_name=None):
        self.new_dialog.set_title("Save device")
        self.new_dialog.label.set_text("Device name:")
        if old_name:
            self.new_dialog.textentry.set_text(old_name)
        else:
            self.new_dialog.textentry.set_text("")
        self.new_dialog.set_transient_for(self.app.main_window_controller.view)
        response = self.new_dialog.run()
        self.new_dialog.hide()
        name = ""
        if response == gtk.RESPONSE_OK:
            name = self.new_dialog.textentry.get_text()
        return name
    
    def protocol_name_dialog(self, old_name=None):
        self.new_dialog.set_title("Save protocol")
        self.new_dialog.label.set_text("Protocol name:")
        if old_name:
            self.new_dialog.textentry.set_text(old_name)
        else:
            self.new_dialog.textentry.set_text("")
        self.new_dialog.set_transient_for(self.app.main_window_controller.view)
        response = self.new_dialog.run()
        self.new_dialog.hide()
        name = ""
        if response == gtk.RESPONSE_OK:
            name = self.new_dialog.textentry.get_text()
        return name

    def save_dmf_device(self, save_as=False, rename=False):
        # if the device has no name, try to get one
        if save_as or rename or self.app.dmf_device.name is None:
            # if the dialog is canceled, name = ""
            name = self.dmf_device_name_dialog(self.app.dmf_device.name)
        else:
            name = self.app.dmf_device.name

        if name:
            # current file name
            src = os.path.join(self.app.config.dmf_device_directory,
                               self.app.dmf_device.name)

            dest = os.path.join(self.app.config.dmf_device_directory,name)

            # if we're renaming, move the old directory
            if rename and self.app.dmf_device.name and os.path.isdir(src):
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
            self.app.config.dmf_device_name = name
            self.app.main_window_controller.update()
        
    def save_protocol(self, save_as=False, rename=False):
        if self.app.dmf_device.name:
            if save_as or rename or self.app.protocol.name is None:
                # if the dialog is canceled, name = ""
                name = self.protocol_name_dialog(self.app.protocol.name)
            else:
                name = self.app.protocol.name

            if name:
                path = os.path.join(self.app.config.dmf_device_directory,
                                    self.app.dmf_device.name,
                                    "protocols")
                if os.path.isdir(path) == False:
                    os.mkdir(path)

                # current file name
                src = os.path.join(path,self.app.protocol.name)
                dest = os.path.join(path,name)
                self.app.protocol.name = name

                # if we're renaming
                if rename and self.app.protocol.name and os.path.isfile(src):
                    shutil.move(src, dest)
                else: # save the file
                    self.app.protocol.save(dest)
    
                # update config
                self.app.config.protocol_name = name
                self.app.main_window_controller.update()
    
    def on_quit(self):
        # TODO: prompt to save if these have been changed 
        self.save_dmf_device()
        self.save_protocol()
        self.app.config.save()