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
import math
import time
import logging
from StringIO import StringIO
from contextlib import closing
import re
import shutil

import gtk
import gobject
import numpy as np

import protocol
from protocol import Protocol
from utility import is_float, is_int, FutureVersionError
from utility.gui import register_shortcuts, textentry_validate
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin, \
    implements, PluginGlobals, ScheduleRequest
from gui.textbuffer_with_undo import UndoableBuffer
from app_context import get_app, plugin_manager


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
            p = Protocol.load(filename)
            for name, data in p.plugin_data.items():
                observers = ExtensionPoint(IPlugin)
                service = observers.service(name)
                if not service:
                    app.main_window_controller.warning("Protocol "
                        "requires the %s plugin, however this plugin is "
                        "not available." % (name))
        except FutureVersionError, why:
            logging.error('''\
Could not open protocol:
    %s
It was created with a newer version of the software.
Protocol is version %s, but only up to version %s is supported with this version of the software.'''\
            % (filename, why.future_version, why.current_version))
        except Exception, why:
            app.main_window_controller.error("Could not open %s. %s" \
                                                  % (filename, why))
        if p:
            plugin_manager.emit_signal("on_protocol_changed", p)
        plugin_manager.emit_signal('on_step_run')

    def on_protocol_changed(self, protocol):
        protocol.plugin_fields = plugin_manager.emit_signal('get_step_fields')
        logging.debug('[ProtocolController] on_protocol_changed(): plugin_fields=%s' % protocol.plugin_fields)
        
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
            'A': self.on_first_step,
            'S': self.on_prev_step,
            'D': self.on_next_step,
            'F': self.on_last_step,
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
        plugin_manager.emit_signal('on_step_run')

    def on_copy_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.copy_step()
        plugin_manager.emit_signal('on_step_run')

    def on_delete_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.delete_step()
        plugin_manager.emit_signal('on_step_run')

    def on_first_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.first_step()
        plugin_manager.emit_signal('on_step_run')

    def on_prev_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.prev_step()
        plugin_manager.emit_signal('on_step_run')

    def on_next_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.next_step()
        plugin_manager.emit_signal('on_step_run')
        
    def on_last_step(self, widget=None, data=None):
        app = get_app()
        app.protocol.last_step()
        plugin_manager.emit_signal('on_step_run')

    def on_new_protocol(self, widget=None, data=None):
        plugin_manager.emit_signal("on_protocol_changed", Protocol())
        plugin_manager.emit_signal('on_step_run')

    def on_load_protocol(self, widget=None, data=None):
        app = get_app()
        dialog = gtk.FileChooserDialog(title="Load protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.path.join(app.get_device_directory(),
                                               app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.load_protocol(filename)
        dialog.destroy()

    def on_rename_protocol(self, widget=None, data=None):
        self.save_protocol(rename=True)
    
    def on_save_protocol(self, widget=None, data=None):
        self.save_protocol()
    
    def on_save_protocol_as(self, widget=None, data=None):
        self.save_protocol(save_as=True)

    def save_protocol(self, save_as=False, rename=False):
        app = get_app()
        name = app.protocol.name
        if app.dmf_device.name:
            if save_as or rename or app.protocol.name is None:
                # if the dialog is cancelled, name = ""
                if name is None:
                    name=""
                name = app.main_window_controller.get_text_input("Save protocol",
                                                                 "Protocol name",
                                                                 name)

            if name:
                path = os.path.join(app.get_device_directory(),
                                    app.dmf_device.name,
                                    "protocols")
                if os.path.isdir(path) == False:
                    os.mkdir(path)

                # current file name
                if app.protocol.name:
                    src = os.path.join(path, app.protocol.name)
                dest = os.path.join(path, name)

                # if the protocol name has changed
                if name != app.protocol.name:
                    app.protocol.name = name
                    plugin_manager.emit_signal("on_protocol_changed", app.protocol)

                # if we're renaming
                if rename and os.path.isfile(src):
                    shutil.move(src, dest)
                else: # save the file
                    app.protocol.save(dest)
    
    def on_textentry_step_duration_focus_out(self, widget=None, data=None):
        self.on_step_duration_changed()

    def on_textentry_step_duration_key_press(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            # user pressed enter
            self.on_step_duration_changed()

    def on_step_duration_changed(self):        
        app = get_app()
        step = app.protocol.current_step()
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        options = step.get_data(dmf_plugin_name)
        options.duration = \
            textentry_validate(self.textentry_step_duration, options.duration, int)
        plugin_manager.emit_signal('on_step_options_changed',
                    [dmf_plugin_name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_voltage_focus_out(self, widget=None, data=None):
        self.on_voltage_changed()

    def on_textentry_voltage_key_press(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            # user pressed enter
            self.on_voltage_changed()

    def on_voltage_changed(self):
        app = get_app()
        step = app.protocol.current_step()
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        options = step.get_data(dmf_plugin_name)
        options.voltage = \
            textentry_validate(self.textentry_voltage, options.voltage, float)
        plugin_manager.emit_signal('on_step_options_changed',
                    [dmf_plugin_name, app.protocol.current_step_number],
                    interface=IPlugin)
        
    def on_textentry_frequency_focus_out(self, widget=None, data=None):
        self.on_frequency_changed()

    def on_textentry_frequency_key_press(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            # user pressed enter
            self.on_frequency_changed()

    def on_frequency_changed(self):
        app = get_app()
        step = app.protocol.current_step()
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        options = step.get_data(dmf_plugin_name)
        options.frequency = \
            textentry_validate(self.textentry_frequency,
                            options.frequency / 1e3,
                            float) * 1e3
        plugin_manager.emit_signal('on_step_options_changed',
                    [dmf_plugin_name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_protocol_repeats_focus_out(self, widget, data=None):
        self.on_protocol_repeats_changed()
    
    def on_textentry_protocol_repeats_key_press(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            # user pressed enter
            self.on_protocol_repeats_changed()
    
    def on_protocol_repeats_changed(self):
        app = get_app()
        app.protocol.n_repeats = \
            textentry_validate(self.textentry_protocol_repeats,
                app.protocol.n_repeats,
                int)
        plugin_manager.emit_signal('on_step_run')

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
        plugin_manager.emit_signal("on_protocol_run")
        
        while app.running:
            self.run_step()

    def pause_protocol(self):
        app = get_app()
        app.running = False
        self.button_run_protocol.set_image(self.builder.get_object(
            "image_play"))
        plugin_manager.emit_signal("on_protocol_pause")
        app.experiment_log_controller.save()
        
    def run_step(self):
        app = get_app()
        if app.realtime_mode or app.running:
            attempt=0
            while True:
                app.experiment_log.add_step(app.protocol.current_step_number)
                if attempt > 0:
                    app.experiment_log.add_data({"attempt":attempt})
                return_codes = plugin_manager.emit_signal("on_step_run")
                if 'Fail' in return_codes.values():
                    self.pause_protocol()
                    app.main_window_controller.error("Protocol failed.")
                    break
                elif 'Repeat' in return_codes.values():
                    attempt+=1
                else:
                    break
        else:
            data = {}
            plugin_manager.emit_signal("on_step_run")

        if app.protocol.current_step_number < len(app.protocol) - 1:
            app.protocol.next_step()
        elif app.protocol.current_repetition < app.protocol.n_repeats - 1:
            app.protocol.next_repetition()
        else: # we're on the last step
            self.pause_protocol()

    def on_step_options_changed(self, plugin, step_number):
        logging.debug('[ProtocolController.on_step_options_changed] plugin=%s, step_number=%s'\
            % (plugin, step_number))
        app = get_app()
        step = app.protocol.steps[step_number]
        if(re.search(r'wheelerlab.dmf_control_board_', plugin)):
            dmf_plugin_name = step.plugin_name_lookup(
                r'wheelerlab.dmf_control_board_', re_pattern=True)
            options = step.get_data(dmf_plugin_name)
            self.textentry_voltage.set_text(str(options.voltage))
            self.textentry_frequency.set_text(str(options.frequency / 1e3))
            self.textentry_step_duration.set_text(str(options.duration))

    def set_app_values(self, values_dict):
        logging.debug('[ProtocolController] set_app_values(): '\
                    'values_dict=%s' % (values_dict,))
        elements = self.AppFields(value=values_dict)
        if not elements.validate():
            raise ValueError('Invalid values: %s' % el.errors)
        values = dict([(k, v.value) for k, v in elements.iteritems() if v.value])
        if 'fps_limit' in values:
            self.grabber.set_fps_limit(values['fps_limit'])
        app = get_app()
        app.set_data(self.name, values)
        plugin_manager.emit_signal('on_app_options_changed', [self.name], interface=IPlugin)

    def on_step_run(self):
        self._update_labels()
        app = get_app()
        step = app.protocol.current_step()
        for plugin_name in step.plugins:
            plugin_manager.emit_signal('on_step_options_changed',
                    [plugin_name,
                    app.protocol.current_step_number],
                    interface=IPlugin)
        with closing(StringIO()) as sio:
            for plugin_name, fields in app.protocol.plugin_fields.iteritems():
                observers = ExtensionPoint(IPlugin)
                service = observers.service(plugin_name)
                print >> sio, '[ProtocolController] plugin.name=%s field_values='\
                        % (plugin_name),
                print >> sio, [service.get_step_value(f) for f in fields]
            logging.debug(sio.getvalue())

    def _update_labels(self):
        app = get_app()
        self.label_step_number.set_text("Step: %d/%d\tRepetition: %d/%d" % 
            (app.protocol.current_step_number + 1,
            len(app.protocol.steps),
            app.protocol.current_repetition + 1,
            app.protocol.n_repeats))
        self.textentry_protocol_repeats.set_text(str(app.protocol.n_repeats))
                
    def on_dmf_device_changed(self, dmf_device):
        plugin_manager.emit_signal("on_protocol_changed", Protocol())

    def on_app_exit(self):
        #TODO: prompt to save if protocol has changed
        self.save_protocol()

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_app_init':
            return [ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        return []

PluginGlobals.pop_env()
