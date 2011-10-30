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
import sys
import gtk
import time

from plugins.dmf_control_board import DmfControlBoard, ConnectionError
from utility import wrap_string, is_float
from plugin_manager import ExtensionPoint, IPlugin

class MicroDropError(Exception):
    pass


class MainWindowController:
    observers = ExtensionPoint(IPlugin)

    def __init__(self, app, builder, signals):
        self.app = app
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "main_window.glade"))
        self.view = builder.get_object("window")
        self.label_connection_status = builder.get_object("label_connection_status")
        self.label_experiment_id = builder.get_object("label_experiment_id")
        self.label_device_name = builder.get_object("label_device_name")
        self.label_protocol_name = builder.get_object("label_protocol_name")
        self.checkbutton_realtime_mode = builder.get_object("checkbutton_realtime_mode")
        self.menu_tools = builder.get_object("menu_tools")
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "about_dialog.glade"))

        signals["on_menu_quit_activate"] = self.on_destroy
        signals["on_menu_about_activate"] = self.on_about
        signals["on_window_destroy"] = self.on_destroy
        signals["on_window_delete_event"] = self.on_delete_event
        signals["on_checkbutton_realtime_mode_toggled"] = \
                self.on_realtime_mode_toggled

        try:
            self.app.control_board = DmfControlBoard()
            self.app.control_board.connect()
            name = self.app.control_board.name()
            version = self.app.control_board.hardware_version()

            # reflash the firmware if it is not the right version
            if self.app.control_board.host_software_version() != \
                self.app.control_board.software_version():
                try:
                    self.app.control_board.flash_firmware()
                except:
                    self.error("Problem flashing firmware")
            firmware = self.app.control_board.software_version()
            self.label_connection_status.set_text(name + " v" + 
              version + "\n\tFirmware: " + str(firmware))
        except ConnectionError, why:
            print why

    def main(self):
        self.update()
        gtk.main()

    def on_delete_event(self, widget, data=None):
        self.app.config_controller.on_quit()
        for observer in self.observers:
            if hasattr(observer, "on_app_exit"):
                observer.on_app_exit()

    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def on_about(self, widget, data=None):
        dialog = self.app.builder.get_object("about_dialog")
        dialog.set_transient_for(self.app.main_window_controller.view)
        dialog.set_version(self.app.version)
        dialog.run()
        dialog.hide()

    def on_realtime_mode_toggled(self, widget, data=None):
        self.update()

    def error(self, message):
        dialog = gtk.MessageDialog(self.view,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_ERROR, 
                                   gtk.BUTTONS_CLOSE, message)
        dialog.run()
        dialog.destroy()                    

    def update(self):
        self.app.realtime_mode = self.checkbutton_realtime_mode.get_active()
        self.app.dmf_device_controller.update()
        self.app.protocol_controller.update()
        
        if self.app.dmf_device.name:
            experiment_id = self.app.experiment_log.get_id()
        else:
            experiment_id = None
        self.label_experiment_id.set_text("Experiment: %s" % str(experiment_id))
        self.label_device_name.set_text("Device: %s" % self.app.dmf_device.name)
        self.label_protocol_name.set_text(
                wrap_string("Protocol: %s" % self.app.protocol.name, 30, "\n\t"))
        
        # process all gtk events
        while gtk.events_pending():
            gtk.main_iteration()
