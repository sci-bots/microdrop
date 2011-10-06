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

import gtk, gobject, os, math, time
import numpy as np
from protocol import Protocol, load as load_protocol
from utility import check_textentry, is_float, is_int
from plugin_manager import ExtensionPoint, IPlugin

class ProtocolController(object):    
    observers = ExtensionPoint(IPlugin)
    
    def __init__(self, app, builder, signals):
        self.app = app
        self.filename = None
        self.previous_voltage = None
        self.previous_frequency = None
        self.textview_notes = builder.get_object("textview_notes")
        self.button_first_step = builder.get_object("button_first_step")
        self.button_prev_step = builder.get_object("button_prev_step")
        self.button_next_step = builder.get_object("button_next_step")
        self.button_last_step = builder.get_object("button_last_step")
        self.button_insert_step = builder.get_object("button_insert_step")
        self.button_copy_step = builder.get_object("button_insert_copy")
        self.button_delete_step = builder.get_object("button_delete_step")
        self.button_run_protocol = builder.get_object("button_run_protocol")
        self.label_step_number = builder.get_object("label_step_number")
        self.menu_save_protocol = builder.get_object("menu_save_protocol")
        self.menu_save_protocol_as = builder.get_object("menu_save_protocol_as")
        self.menu_load_protocol = builder.get_object("menu_load_protocol")
        self.menu_add_frequency_sweep = builder.get_object("menu_add_frequency_sweep")
        self.textentry_voltage = builder.get_object("textentry_voltage")
        self.textentry_frequency = builder.get_object("textentry_frequency")
        self.textentry_step_time = builder.get_object("textentry_step_time")
        self.image_play = builder.get_object("image_play")
        self.image_pause = builder.get_object("image_pause")
        self.textentry_protocol_repeats = builder.get_object("textentry_protocol_repeats")

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

        # delete all steps
        while len(self.app.protocol.steps) > 1:
            self.app.protocol.delete_step()
        self.app.protocol.delete_step() # still need to delete the first step
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
            self.app.protocol = load_protocol(self.filename)
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

    """
    def on_feedback_toggled(self, widget, data=None):
        if self.checkbutton_feedback.get_active():
            if self.app.protocol.current_step().feedback_options is None:
                self.app.protocol.current_step().feedback_options = \
                    FeedbackOptions()
            self.button_step_type_options.set_sensitive(True)
            self.textentry_step_time.set_sensitive(False)
        else:
            self.app.protocol.current_step().feedback_options = None
            self.button_step_type_options.set_sensitive(False)
            self.textentry_step_time.set_sensitive(True)
    """
            
    def on_run_protocol(self, widget, data=None):
        if self.app.running:
            self.pause_protocol()
            for observer in self.observers:
                if hasattr(observer, "on_protocol_pause"):
                    observer.on_protocol_pause()
        else:
            self.run_protocol()
            for observer in self.observers:
                if hasattr(observer, "on_protocol_run"):
                    observer.on_protocol_run()

    def run_protocol(self):
        self.app.running = True
        self.run_step()

    def pause_protocol(self):
        self.app.running = False
        
    def run_step(self):
        self.app.main_window_controller.update()
        if self.app.control_board.connected():
            data = {"step":self.app.protocol.current_step_number,
                    "time":time.time()}
            
            """            
            feedback_options = \
                self.protocol.current_step().feedback_options
            """
            
            state = self.app.protocol.current_step().state_of_channels

            """
            if feedback_options: # run this step with feedback
                ad_channel = 1

                # measure droplet impedance
                self.control_board.set_series_resistor(ad_channel, 2)
                
                impedance = self.control_board.MeasureImpedance(
                           feedback_options.sampling_time_ms,
                           feedback_options.n_samples,
                           feedback_options.delay_between_samples_ms,
                           state)
                V_fb = impedance[0::2]
                Z_fb = impedance[1::2]
                V_total = self.protocol.current_step().voltage
                Z_device = Z_fb*(V_total/V_fb-1)
                data["Z_device"] = Z_device
                data["V_fb"] = V_fb
                data["Z_fb"] = Z_fb

                # measure the voltage waveform for each series resistor
                for i in range(0,4):
                    self.control_board.set_series_resistor(ad_channel,i)
                    voltage_waveform = self.control_board.SampleVoltage(
                                [ad_channel], 1000, 1, 0, state)
                    data["voltage waveform (Resistor=%.1f kOhms)" %
                         (self.control_board.series_resistor(ad_channel)/1000.0)] = \
                         voltage_waveform
            else:   # run without feedback
                self.control_board.set_state_of_all_channels(state)
                time.sleep(self.protocol.current_step().time/1000.0)
            """

            self.app.control_board.set_state_of_all_channels(state)
            time.sleep(self.app.protocol.current_step().time/1000.0)

            """
            # TODO: temproary hack to measure temperature
            state = np.zeros(len(state))
            voltage_waveform = self.control_board.SampleVoltage(
                        [15], 10, 1, 0, state)
            temp = np.mean(voltage_waveform/1024.0*5.0/0.01)
            print temp
            data["AD595 temp"] = temp
            """
            self.app.experiment_log.add_data(data)
        else: # run through protocol (even though device is not connected)
            time.sleep(self.app.protocol.current_step().time/1000.0)
                
        if self.app.protocol.current_step_number < len(self.app.protocol)-1:
            self.app.protocol.next_step()
        elif self.app.protocol.current_repetition < self.app.protocol.n_repeats-1:
            self.app.protocol.next_repetition()
        else: # we're on the last step
            self.app.running = False
            self.app.experiment_log_controller.save()

        if self.app.running:
            self.run_step()

    def update(self):
        self.textentry_step_time.set_text(str(self.app.protocol.current_step().time))
        self.textentry_voltage.set_text(str(self.app.protocol.current_step().voltage))
        self.textentry_frequency.set_text(str(self.app.protocol.current_step().frequency/1e3))
        self.label_step_number.set_text("Step: %d/%d\tRepetition: %d/%d" % 
            (self.app.protocol.current_step_number+1, len(self.app.protocol.steps),
             self.app.protocol.current_repetition+1, self.app.protocol.n_repeats))

        if self.app.running:
            self.button_run_protocol.set_image(self.image_pause)
        else:
            self.button_run_protocol.set_image(self.image_play)

        if self.app.control_board.connected() and \
            (self.app.realtime_mode or self.app.running):
            if self.app.func_gen.is_connected():
                self.app.func_gen.set_voltage(self.app.protocol.current_step().voltage*math.sqrt(2)/200)
                self.app.func_gen.set_frequency(self.app.protocol.current_step().frequency)
            else:
                self.app.control_board.set_actuation_voltage(float(self.app.protocol.current_step().voltage))
                self.app.control_board.set_actuation_frequency(float(self.app.protocol.current_step().frequency))
            if self.app.running is False:
                state = self.app.protocol.state_of_all_channels()
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