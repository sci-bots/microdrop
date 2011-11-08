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

from utility import wrap_string, is_float
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin, \
    implements, emit_signal

class MicroDropError(Exception):
    pass


class MainWindowController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.app = None
        self.name = "microdrop.gui.main_window_controller"
        self.builder = None
        self.view = None
        self.label_connection_status = None
        self.label_experiment_id = None
        self.label_device_name = None
        self.label_protocol_name = None
        self.checkbutton_realtime_mode = None
        self.menu_tools = None
        self.menu_view = None
        gtk.link_button_set_uri_hook(self.on_url_clicked)
        
    def on_app_init(self, app):
        self.app = app
        app.builder.add_from_file(os.path.join("gui",
                                               "glade",
                                               "main_window.glade"))
        self.view = app.builder.get_object("window")
        self.label_connection_status = app.builder.get_object("label_connection_status")
        self.label_experiment_id = app.builder.get_object("label_experiment_id")
        self.label_device_name = app.builder.get_object("label_device_name")
        self.label_protocol_name = app.builder.get_object("label_protocol_name")
        self.checkbutton_realtime_mode = app.builder.get_object("checkbutton_realtime_mode")
        self.menu_tools = app.builder.get_object("menu_tools")
        self.menu_view = app.builder.get_object("menu_view")

        app.signals["on_menu_quit_activate"] = self.on_destroy
        app.signals["on_menu_about_activate"] = self.on_about
        app.signals["on_menu_experiment_logs_activate"] = \
            self.on_menu_experiment_logs_activate
        app.signals["on_window_destroy"] = self.on_destroy
        app.signals["on_window_delete_event"] = self.on_delete_event
        app.signals["on_checkbutton_realtime_mode_toggled"] = \
                self.on_realtime_mode_toggled
        signals["on_menu_options_activate"] = self.on_menu_options_activate

        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join("gui",
                                                "glade",
                                                "about_dialog.glade"))
        self.app.main_window_controller = self

    def main(self):
        self.update()
        gtk.main()

    def on_delete_event(self, widget, data=None):
        emit_signal("on_app_exit")

    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def on_about(self, widget, data=None):
        dialog = self.builder.get_object("about_dialog")
        dialog.set_transient_for(self.app.main_window_controller.view)
        dialog.set_version(self.app.version)
        dialog.run()
        dialog.hide()

    def on_menu_experiment_logs_activate(self, widget, data=None):
        self.app.experiment_log_controller.on_window_show(widget, data)

    def on_realtime_mode_toggled(self, widget, data=None):
        self.update()

    def on_menu_options_activate(self, widget, data=None):
        from options_controller import OptionsController

        print 'selected options menu'
        OptionsController(self.app).run()
        self.update()

    def error(self, message):
        dialog = gtk.MessageDialog(self.view,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_ERROR, 
                                   gtk.BUTTONS_CLOSE, message)
        dialog.run()
        dialog.destroy()                    

    def warning(self, message):
        dialog = gtk.MessageDialog(self.view,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_WARNING, 
                                   gtk.BUTTONS_CLOSE, message)
        dialog.run()
        dialog.destroy()                    

    def update(self):
        self.app.realtime_mode = self.checkbutton_realtime_mode.get_active()
        self.app.dmf_device_controller.update()
        self.app.protocol_controller.update()
        
        if self.app.dmf_device.name:
            experiment_id = self.app.experiment_log.get_next_id()
        else:
            experiment_id = None
        self.label_experiment_id.set_text("Experiment: %s" % str(experiment_id))
        self.label_device_name.set_text("Device: %s" % self.app.dmf_device.name)
        self.label_protocol_name.set_text(
                wrap_string("Protocol: %s" % self.app.protocol.name, 30, "\n\t"))
        
        # process all gtk events
        while gtk.events_pending():
            gtk.main_iteration()

    def on_url_clicked(self, widget, data=None):
        print "url clicked"
