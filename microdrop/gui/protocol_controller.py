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

import numpy as np

from protocol import Protocol, load as load_protocol
from utility import check_textentry, is_float, is_int
from plugin_manager import ExtensionPoint, IPlugin


class ProtocolController(object):    
    observers = ExtensionPoint(IPlugin)
    
    def __init__(self, app, builder, signals):
        self.app = app
        self.builder = builder
        self.filename = None
        self.previous_voltage = None
        self.previous_frequency = None
        signals["on_button_insert_step_clicked"] = self.on_insert_step
        signals["on_button_delete_step_clicked"] = self.on_delete_step
        signals["on_button_copy_step_clicked"] = self.on_copy_step
        signals["on_button_first_step_clicked"] = self.on_first_step
        signals["on_button_prev_step_clicked"] = self.on_prev_step
        signals["on_button_next_step_clicked"] = self.on_next_step
        signals["on_button_last_step_clicked"] = self.on_last_step
        signals["on_button_run_protocol_clicked"] = self.on_run_protocol
        signals["on_menu_new_protocol_activate"] = self.on_new_protocol
        signals["on_menu_load_protocol_activate"] = self.on_load_protocol
        signals["on_menu_rename_protocol_activate"] = self.on_rename_protocol
        signals["on_menu_save_protocol_activate"] = self.on_save_protocol
        signals["on_menu_save_protocol_as_activate"] = self.on_save_protocol_as
        signals["on_menu_add_frequency_sweep_activate"] = self.on_add_frequency_sweep
        signals["on_textentry_voltage_focus_out_event"] = \
                self.on_textentry_voltage_focus_out
        signals["on_textentry_voltage_key_press_event"] = \
                self.on_textentry_voltage_key_press
        signals["on_textentry_frequency_focus_out_event"] = \
                self.on_textentry_frequency_focus_out
        signals["on_textentry_frequency_key_press_event"] = \
                self.on_textentry_frequency_key_press
        signals["on_textentry_protocol_repeats_focus_out_event"] = \
                self.on_textentry_protocol_repeats_focus_out
        signals["on_textentry_protocol_repeats_key_press_event"] = \
                self.on_textentry_protocol_repeats_key_press
        signals["on_textentry_step_time_focus_out_event"] = \
                self.on_textentry_step_time_focus_out
        signals["on_textentry_step_time_key_press_event"] = \
                self.on_textentry_step_time_key_press

        store = gtk.ListStore(gobject.TYPE_STRING)
        cell = gtk.CellRendererText()
        store.append(["Normal"])

    def on_insert_step(self, widget, data=None):
        self.app.protocol.insert_step()
        self.app.main_window_controller.update()

    def on_copy_step(self, widget, data=None):
        self.app.protocol.copy_step()
        self.app.main_window_controller.update()

    def on_delete_step(self, widget, data=None):
        self.app.protocol.delete_step()
        self.app.main_window_controller.update()

    def on_first_step(self, widget=None, data=None):
        self.app.protocol.first_step()
        self.app.main_window_controller.update()

    def on_prev_step(self, widget=None, data=None):
        self.app.protocol.prev_step()
        self.app.main_window_controller.update()

    def on_next_step(self, widget=None, data=None):
        self.app.protocol.next_step()
        self.app.main_window_controller.update()

    def on_last_step(self, widget=None, data=None):
        self.app.protocol.last_step()
        self.app.main_window_controller.update()

    def on_new_protocol(self, widget, data=None):
        self.filename = None
        # delete all steps (this is necessary so that plugins will also
        # clear all steps
        while len(self.app.protocol.steps) > 1:
            self.app.protocol.delete_step()
        self.app.protocol.delete_step() # still need to delete the first step
        self.app.protocol = Protocol(self.app.dmf_device.max_channel()+1)
        self.app.main_window_controller.update()

    def on_load_protocol(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title="Load protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.path.join("devices",
                                               self.app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.filename = dialog.get_filename()
            try:
                self.app.protocol = load_protocol(self.filename)
            except:
                self.app.main_window_controller.error("Could not open %s" % self.filename)
        dialog.destroy()
        self.app.main_window_controller.update()

    def on_rename_protocol(self, widget, data=None):
        self.app.config_controller.save_protocol(rename=True)
    
    def on_save_protocol(self, widget, data=None):
        self.app.config_controller.save_protocol()
    
    def on_save_protocol_as(self, widget, data=None):
        self.app.config_controller.save_protocol(save_as=True)
    
    def on_add_frequency_sweep(self, widget, data=None):
        AddFrequencySweepDialog(self.app).run()
        self.app.main_window_controller.update()

    def on_textentry_step_time_focus_out(self, widget, data=None):
        self.on_step_time_changed()

    def on_textentry_step_time_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_step_time_changed()

    def on_step_time_changed(self):        
        self.app.protocol.current_step().time = \
            check_textentry(self.textentry_step_time,
                            self.app.protocol.current_step().time,
                            int)

    def on_textentry_voltage_focus_out(self, widget, data=None):
        self.on_voltage_changed()

    def on_textentry_voltage_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_voltage_changed()

    def on_voltage_changed(self):
        self.app.protocol.current_step().voltage = \
            check_textentry(self.textentry_voltage,
                            self.app.protocol.current_step().voltage,
                            float)
        self.update()
        
    def on_textentry_frequency_focus_out(self, widget, data=None):
        self.on_frequency_changed()

    def on_textentry_frequency_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_frequency_changed()

    def on_frequency_changed(self):
        self.app.protocol.current_step().frequency = \
            check_textentry(self.textentry_frequency,
                            self.app.protocol.current_step().frequency/1e3,
                            float)*1e3
        self.update()

    def on_textentry_protocol_repeats_focus_out(self, widget, data=None):
        self.on_protocol_repeats_changed()
    
    def on_textentry_protocol_repeats_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_protocol_repeats_changed()
    
    def on_protocol_repeats_changed(self):
        self.app.protocol.n_repeats = \
            check_textentry(self.textentry_protocol_repeats,
                            self.app.protocol.n_repeats,
                            int)
        self.update()
            
    def on_run_protocol(self, widget, data=None):
        if self.app.running:
            self.pause_protocol()
        else:
            self.run_protocol()

    def run_protocol(self):
        if self.app.control_board.connected() and\
            self.app.control_board.number_of_channels() < \
            self.app.protocol.n_channels:
            self.app.main_window_controller.warning("Warning: currently "
                "connected board does not have enough channels for this "
                "protocol.")
        self.app.running = True
        self.builder.get_object("button_run_protocol"). \
            set_image(self.builder.get_object("image_pause"))
        for observer in self.observers:
            if hasattr(observer, "on_protocol_run"):
                observer.on_protocol_run()
        self.run_step()

    def pause_protocol(self):
        self.app.running = False
        self.builder.get_object("button_run_protocol"). \
            set_image(self.builder.get_object("image_play"))
        for observer in self.observers:
            if hasattr(observer, "on_protocol_pause"):
                observer.on_protocol_pause()
        
    def run_step(self):
        self.app.main_window_controller.update()
        
        # run through protocol (even though device is not connected)
        if self.app.control_board.connected()==False:
            t = time.time()
            while time.time()-t < self.app.protocol.current_step().time/1000.0:
                while gtk.events_pending():
                    gtk.main_iteration()

        if self.app.protocol.current_step_number < len(self.app.protocol)-1:
            self.app.protocol.next_step()
        elif self.app.protocol.current_repetition < self.app.protocol.n_repeats-1:
            self.app.protocol.next_repetition()
        else: # we're on the last step
            self.app.experiment_log_controller.save()
            self.pause_protocol()

        if self.app.running:
            self.run_step()

    def update(self):
        self.builder.get_object("textentry_step_time"). \
            set_text(str(self.app.protocol.current_step().time))
        self.builder.get_object("textentry_voltage"). \
            set_text(str(self.app.protocol.current_step().voltage))
        self.builder.get_object("textentry_frequency"). \
            set_text(str(self.app.protocol.current_step().frequency/1e3))
        self.builder.get_object("label_step_number"). \
            set_text("Step: %d/%d\tRepetition: %d/%d" % 
            (self.app.protocol.current_step_number+1, len(self.app.protocol.steps),
             self.app.protocol.current_repetition+1, self.app.protocol.n_repeats))

        if self.app.control_board.connected() and \
            (self.app.realtime_mode or self.app.running):
            if self.app.func_gen.is_connected():
                self.app.func_gen.set_voltage(self.app.protocol.current_step().voltage*math.sqrt(2)/200)
                self.app.func_gen.set_frequency(self.app.protocol.current_step().frequency)
            else:
                self.app.control_board.set_waveform_voltage(float(self.app.protocol.current_step().voltage)*math.sqrt(2)/100)
                self.app.control_board.set_waveform_frequency(float(self.app.protocol.current_step().frequency))
            if self.app.realtime_mode:
                state = self.app.protocol.state_of_all_channels()
                max_channels = self.app.control_board.number_of_channels() 
                if len(state) >  max_channels:
                    if len(np.nonzero(state[max_channels:]>=1)[0]):
                        self.app.main_window_controller.warning("One or more "
                            "channels that are currently on are not available.")
                    state = state[0:max_channels]
                elif len(state) < max_channels:
                    state = np.concatenate([state, np.zeros(max_channels-len(state), int)])
                else:
                    assert(len(state)==max_channels)
                self.app.control_board.set_state_of_all_channels(state)

        for observer in self.observers:
            if hasattr(observer, "on_protocol_update"):
                observer.on_protocol_update()

class AddFrequencySweepDialog:
    def __init__(self, app):
        self.app = app
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "frequency_sweep_dialog.glade"))
        self.dialog = builder.get_object("frequency_sweep_dialog")
        self.dialog.set_transient_for(app.main_window_controller.view)
        self.textentry_start_freq = \
            builder.get_object("textentry_start_freq")
        self.textentry_end_freq = \
            builder.get_object("textentry_end_freq")
        self.textentry_n_steps = \
            builder.get_object("textentry_n_steps")
        self.textentry_start_freq.set_text("0.1")
        self.textentry_end_freq.set_text("1e2")
        self.textentry_n_steps.set_text("30")
        
    def run(self):
        response = self.dialog.run()
        if response == gtk.RESPONSE_OK:
            start_freq = self.textentry_start_freq.get_text() 
            end_freq = self.textentry_end_freq.get_text() 
            number_of_steps = self.textentry_n_steps.get_text()
            if is_float(start_freq) == False:
                self.app.main_window_controller.error("Invalid start frequency.")
            elif is_float(end_freq) == False:
                self.app.main_window_controller.error("Invalid end frequency.")
            elif is_int(number_of_steps) == False or number_of_steps < 1:
                self.app.main_window_controller.error("Invalid number of steps.")
            elif end_freq < start_freq:
                self.app.main_window_controller.error("End frequency must be greater than the start frequency.")
            else:
                frequencies = np.logspace(np.log10(float(start_freq)),
                                          np.log10(float(end_freq)),
                                          int(number_of_steps))
                for frequency in frequencies:
                    self.app.protocol.current_step().frequency = frequency*1e3
                    self.app.protocol.copy_step()
        self.dialog.hide()
        return response