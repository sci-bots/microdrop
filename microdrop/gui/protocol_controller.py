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

import gtk
import gobject
import os
import math
import time
import logging
from StringIO import StringIO
from contextlib import closing

import numpy as np

import protocol
from protocol import Protocol
from utility import check_textentry, is_float, is_int
from utility.gui import register_shortcuts
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin, \
    implements, emit_signal, PluginGlobals
from gui.textbuffer_with_undo import UndoableBuffer
from app_context import get_app


PluginGlobals.push_env('microdrop')


class ProtocolController(SingletonPlugin):
    implements(IPlugin)
    
    def __init__(self):
        self.name = "microdrop.gui.protocol_controller"
        self.builder = None
        self.textentry_step_duration = None
        self.textentry_voltage = None
        self.textentry_frequency = None
        self.label_step_number = None
        self.textentry_voltage = None
        self.textentry_frequency = None
        self.label_step_number = None
        self.button_run_protocol = None
        self.textentry_protocol_repeats = None

    def load_protocol(self, filename):
        app = get_app()
        p = None
        try:
            p = protocol.load(filename)
            for (name, (version, data)) in p.plugin_data.items():
                observers = ExtensionPoint(IPlugin)
                service = observers.service(name)
                if service:
                    service.on_protocol_load(version, data)
                else:
                    app.main_window_controller.warning("Protocol "
                        "requires the %s plugin, however this plugin is "
                        "not available." % (name))
        except Exception, why:
            app.main_window_controller.error("Could not open %s. %s" \
                                                  % (filename, why))
        if p:
            emit_signal("on_protocol_changed", p)

    def on_protocol_changed(self, protocol):
        protocol.plugin_fields = emit_signal('get_step_fields', by_observer=True)
        logging.info('[ProtocolController] on_protocol_changed(): plugin_fields=%s' % protocol.plugin_fields)
        
    def on_app_init(self):
        app = get_app()
        self.builder = app.builder
        
        self.textentry_notes = self.builder.get_object("textview_notes")
        self.textentry_notes.set_buffer(UndoableBuffer())
        self.textentry_step_duration = self.builder. \
            get_object("textentry_step_duration")
        self.textentry_voltage = self.builder.get_object("textentry_voltage")
        self.textentry_frequency = self.builder. \
            get_object("textentry_frequency")
        self.label_step_number = self.builder.get_object("label_step_number")
        self.textentry_voltage = self.builder.get_object("textentry_voltage")
        self.textentry_frequency = self.builder. \
            get_object("textentry_frequency")
        self.label_step_number = self.builder.get_object("label_step_number")
        self.textentry_protocol_repeats = self.builder.get_object(
            "textentry_protocol_repeats")        
        self.button_run_protocol = self.builder.get_object("button_run_protocol")
        
        app.signals["on_button_insert_step_clicked"] = self.on_insert_step
        app.signals["on_button_delete_step_clicked"] = self.on_delete_step
        app.signals["on_button_copy_step_clicked"] = self.on_copy_step
        app.signals["on_button_first_step_clicked"] = self.on_first_step
        app.signals["on_button_prev_step_clicked"] = self.on_prev_step
        app.signals["on_button_next_step_clicked"] = self.on_next_step
        app.signals["on_button_last_step_clicked"] = self.on_last_step
        app.signals["on_button_run_protocol_clicked"] = self.on_run_protocol
        app.signals["on_menu_new_protocol_activate"] = self.on_new_protocol
        app.signals["on_menu_load_protocol_activate"] = self.on_load_protocol
        app.signals["on_menu_rename_protocol_activate"] = self.on_rename_protocol
        app.signals["on_menu_save_protocol_activate"] = self.on_save_protocol
        app.signals["on_menu_save_protocol_as_activate"] = self.on_save_protocol_as
        app.signals["on_textentry_voltage_focus_out_event"] = \
                self.on_textentry_voltage_focus_out
        app.signals["on_textentry_voltage_key_press_event"] = \
                self.on_textentry_voltage_key_press
        app.signals["on_textentry_frequency_focus_out_event"] = \
                self.on_textentry_frequency_focus_out
        app.signals["on_textentry_frequency_key_press_event"] = \
                self.on_textentry_frequency_key_press
        app.signals["on_textentry_protocol_repeats_focus_out_event"] = \
                self.on_textentry_protocol_repeats_focus_out
        app.signals["on_textentry_protocol_repeats_key_press_event"] = \
                self.on_textentry_protocol_repeats_key_press
        app.signals["on_textentry_step_duration_focus_out_event"] = \
                self.on_textentry_step_duration_focus_out
        app.signals["on_textentry_step_duration_key_press_event"] = \
                self.on_textentry_step_duration_key_press
        app.protocol_controller = self
        self._register_shortcuts()

    def _register_shortcuts(self):
        app = get_app()
        view = app.main_window_controller.view
        shortcuts = {
            'space': self.on_run_protocol,
            '<Control>Left': self.on_prev_step,
            '<Control>Right': self.on_next_step,
            'Home': self.on_first_step,
            'End': self.on_last_step,
            'Delete': self.on_delete_step,
        }
        register_shortcuts(view, shortcuts,
                    disabled_widgets=[self.textentry_notes])

        notes_shortcuts = {
            '<Control>z': self.textentry_notes.get_buffer().undo,
            '<Control>y': self.textentry_notes.get_buffer().redo,
        }
        register_shortcuts(view, notes_shortcuts,
                    enabled_widgets=[self.textentry_notes])

    def on_insert_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.insert_step()
        emit_signal("on_insert_protocol_step")
        app.main_window_controller.update()

    def on_copy_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.copy_step()
        emit_signal("on_insert_protocol_step")
        app.main_window_controller.update()

    def on_delete_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.delete_step()
        emit_signal("on_delete_protocol_step")
        app.main_window_controller.update()

    def on_first_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.first_step()
        app.main_window_controller.update()

    def on_prev_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.prev_step()
        app.main_window_controller.update()

    def on_next_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.next_step()
        app.main_window_controller.update()

    def on_last_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.last_step()
        app.main_window_controller.update()

    def on_new_protocol(self, widget=None, data=None):
        app = get_app()
        filename = None
        p = Protocol(app.dmf_device.max_channel()+1)
        emit_signal("on_protocol_changed", p)
        app.main_window_controller.update()

    def on_load_protocol(self, widget=None, data=None):
        app = get_app()
        dialog = gtk.FileChooserDialog(title="Load protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.path.join(app.config.dmf_device_directory,
                                               app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.load_protocol(filename)
        dialog.destroy()
        app.main_window_controller.update()

    def on_rename_protocol(self, widget=None, data=None):
        app = get_app()
        app.config_controller.save_protocol(rename=True)
    
    def on_save_protocol(self, widget=None, data=None):
        app = get_app()
        app.config_controller.save_protocol()
    
    def on_save_protocol_as(self, widget=None, data=None):
        app = get_app()
        app.config_controller.save_protocol(save_as=True)
    
    def on_textentry_step_duration_focus_out(self, widget=None, data=None):
        self.on_step_duration_changed()

    def on_textentry_step_duration_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_step_duration_changed()

    def on_step_duration_changed(self):        
        app = get_app()
        step = app.protocol.current_step()
        step.duration = \
            check_textentry(self.textentry_step_duration, step.duration, int)

    def on_textentry_voltage_focus_out(self, widget=None, data=None):
        self.on_voltage_changed()

    def on_textentry_voltage_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_voltage_changed()

    def on_voltage_changed(self):
        app = get_app()
        step = app.protocol.current_step()
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        options = step.get_data(dmf_plugin_name)
        options.voltage = \
            check_textentry(self.textentry_voltage, options.voltage, float)
        self.update()
        
    def on_textentry_frequency_focus_out(self, widget=None, data=None):
        self.on_frequency_changed()

    def on_textentry_frequency_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_frequency_changed()

    def on_frequency_changed(self):
        app = get_app()
        step = app.protocol.current_step()
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        options = step.get_data(dmf_plugin_name)
        options.frequency = \
            check_textentry(self.textentry_frequency,
                            options.frequency/1e3,
                            float)*1e3
        self.update()

    def on_textentry_protocol_repeats_focus_out(self, widget, data=None):
        self.on_protocol_repeats_changed()
    
    def on_textentry_protocol_repeats_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_protocol_repeats_changed()
    
    def on_protocol_repeats_changed(self):
        app = get_app()
        app.protocol.n_repeats = \
            check_textentry(self.textentry_protocol_repeats,
                            app.protocol.n_repeats,
                            int)
        self.update()
            
    def on_run_protocol(self, widget=None, data=None):
        app = get_app()
        if app.running:
            self.pause_protocol()
        else:
            self.run_protocol()

    def run_protocol(self):
        app = get_app()
        app.running = True
        self.button_run_protocol.set_image(self.builder.get_object(
            "image_pause"))
        emit_signal("on_protocol_run")
        
        while app.running:
            self.run_step()

    def pause_protocol(self):
        app = get_app()
        app.running = False
        self.button_run_protocol.set_image(self.builder.get_object(
            "image_play"))
        emit_signal("on_protocol_pause")
        app.experiment_log_controller.save()
        emit_signal("on_experiment_log_changed", app.experiment_log)        
        
    def run_step(self):
        app = get_app()
        app.main_window_controller.update()
        
        if app.protocol.current_step_number < len(app.protocol) - 1:
            app.protocol.next_step()
        elif app.protocol.current_repetition < app.protocol.n_repeats - 1:
            app.protocol.next_repetition()
        else: # we're on the last step
            self.pause_protocol()

    def update(self):
        app = get_app()
        step = app.protocol.current_step()
        self.label_step_number.set_text("Step: %d/%d\tRepetition: %d/%d" % 
            (app.protocol.current_step_number + 1,
            len(app.protocol.steps),
            app.protocol.current_repetition + 1,
            app.protocol.n_repeats))

        if app.realtime_mode or app.running:
            attempt=0
            while True:
                data = {"step": app.protocol.current_step_number, 
                        "time": time.time() - app.experiment_log.start_time()}
                if attempt > 0:
                    data["attempt"] = attempt                
                return_codes = emit_signal("on_protocol_update", data)
                if return_codes.count("Fail") > 0:
                    self.pause_protocol()
                    app.main_window_controller.error("Protocol failed.")
                    break
                elif return_codes.count("Repeat") > 0:
                    app.experiment_log.add_data(data)
                    attempt+=1
                else:
                    app.experiment_log.add_data(data)
                    break
        else:
            data = {}
            emit_signal("on_protocol_update", data)
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        logging.debug('[ProtocolController] dmf_plugin_name=%s' % dmf_plugin_name)
        options = step.get_data(dmf_plugin_name)

        self.textentry_step_duration.set_text(str(step.duration))
        self.textentry_voltage.set_text(str(options.voltage))
        self.textentry_frequency.set_text(str(options.frequency / 1e3))

    def on_protocol_update(self, data=None):
        app = get_app()
        with closing(StringIO()) as sio:
            for plugin_name, fields in app.protocol.plugin_fields.iteritems():
                observers = ExtensionPoint(IPlugin)
                service = observers.service(plugin_name)
                print >> sio, '[ProtocolController] plugin.name=%s field_values='\
                        % (plugin_name),
                print >> sio, [service.get_step_value(f) for f in fields]
            logging.debug(sio.getvalue())
                
    def on_dmf_device_changed(self, dmf_device):
        emit_signal("on_protocol_changed", Protocol(dmf_device.max_channel() + 1))


PluginGlobals.pop_env()
