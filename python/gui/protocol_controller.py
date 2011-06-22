import gtk
import pickle
import gobject
import matplotlib.pyplot as plt
from protocol import Protocol, MeasureImpedance

def isfloat(s):
    try: return (float(s), True)[1]
    except (ValueError, TypeError), e: return False

def isint(s):
    try: return (int(s), True)[1]
    except (ValueError, TypeError), e: return False

class ProtocolController():
    def __init__(self, app, builder, signals):
        self.data = []
        self.app = app
        self.timer_id = None

        self.button_first_step = builder.get_object("button_first_step")
        self.button_prev_step = builder.get_object("button_prev_step")
        self.button_next_step = builder.get_object("button_next_step")
        self.button_last_step = builder.get_object("button_last_step")
        self.button_insert_step = builder.get_object("button_insert_step")
        self.button_delete_step = builder.get_object("button_delete_step")
        self.label_step_number = builder.get_object("label_step_number")
        self.menu_save_protocol = builder.get_object("menu_save_protocol")
        self.menu_save_protocol_as = builder.get_object("menu_save_protocol_as")
        self.menu_load_protocol = builder.get_object("menu_load_protocol")
        self.menu_add_frequency_sweep = builder.get_object("menu_add_frequency_sweep")
        self.menu_add_electrode_sweep = builder.get_object("menu_add_electrode_sweep")
        self.menu_run_protocol = builder.get_object("menu_run_protocol")
        self.textentry_voltage = builder.get_object("textentry_voltage")
        self.textentry_frequency = builder.get_object("textentry_frequency")
        self.textentry_step_time = builder.get_object("textentry_step_time")
        self.checkbutton_measure_impedance = \
            builder.get_object("checkbutton_measure_impedance")

        signals["on_button_insert_step_clicked"] = self.on_insert_step
        signals["on_button_delete_step_clicked"] = self.on_delete_step
        signals["on_button_first_step_clicked"] = self.on_first_step
        signals["on_button_prev_step_clicked"] = self.on_prev_step
        signals["on_button_next_step_clicked"] = self.on_next_step
        signals["on_button_last_step_clicked"] = self.on_last_step
        signals["on_menu_new_protocol_activate"] = self.on_new_protocol
        signals["on_menu_save_protocol_activate"] = self.on_save_protocol
        signals["on_menu_save_protocol_as_activate"] = self.on_save_protocol_as
        signals["on_menu_load_protocol_activate"] = self.on_load_protocol
        signals["on_menu_run_protocol_activate"] = self.on_run_protocol
        signals["on_menu_add_frequency_sweep_activate"] = self.on_add_frequency_sweep
        signals["on_menu_add_electrode_sweep_activate"] = self.on_add_electrode_sweep
        signals["on_textentry_voltage_focus_out_event"] = \
                self.on_textentry_voltage_focus_out
        signals["on_textentry_voltage_key_press_event"] = \
                self.on_textentry_voltage_key_press
        signals["on_textentry_frequency_focus_out_event"] = \
                self.on_textentry_frequency_focus_out
        signals["on_textentry_frequency_key_press_event"] = \
                self.on_textentry_frequency_key_press
        signals["on_textentry_step_time_focus_out_event"] = \
                self.on_textentry_step_time_focus_out
        signals["on_textentry_step_time_key_press_event"] = \
                self.on_textentry_step_time_key_press
        signals["on_checkbutton_measure_impedance_toggled"] = \
                self.on_measure_impedance_toggled

    def is_running(self):
        if self.timer_id:
            return True
        else:
            return False

    def on_insert_step(self, widget, data=None):
        self.app.protocol.insert_step()
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
        self.app.protocol = Protocol()
        self.app.main_window_controller.update()

    def on_save_protocol(self, widget, data=None):
        print "save protcol"
        #TODO

    def on_save_protocol_as(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title=None,
                                       action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_SAVE_AS,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder("protocols")
        dialog.set_current_name("new")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            file_name = dialog.get_filename()
            output = open(file_name, 'wb')
            pickle.dump(self.app.protocol, output, -1)
            output.close()
        dialog.destroy()

    def on_load_protocol(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title=None,
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder("protocols")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            file_name = dialog.get_filename()
            f = open(file_name, 'rb')
            self.app.protocol = pickle.load(f)
            f.close()
        dialog.destroy()
        self.app.main_window_controller.update()

    def on_add_frequency_sweep(self, widget, data=None):
        print "add frequency sweep"

    def on_add_electrode_sweep(self, widget, data=None):
        print "add electrode sweep"

    def on_textentry_step_time_focus_out(self, widget, data=None):
        self.on_step_time_changed()

    def on_textentry_step_time_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_step_time_changed()

    def on_step_time_changed(self):
        step_time = self.textentry_step_time.get_text()
        if isint(step_time):
            self.app.protocol.current_step().time = int(step_time)
        else:
            print "error" # TODO dialog error
            self.textentry_step_time.set_text(str(self.app.protocol.current_step().time))

    def on_textentry_voltage_focus_out(self, widget, data=None):
        self.on_voltage_changed()

    def on_textentry_voltage_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_voltage_changed()

    def on_voltage_changed(self):
        voltage = self.textentry_voltage.get_text()
        if isint(voltage):
            self.app.set_voltage(int(voltage))
        else:
            print "error" # TODO dialog error
            self.textentry_voltage.set_text(str(self.app.protocol.current_step().voltage))

    def on_textentry_frequency_focus_out(self, widget, data=None):
        self.on_frequency_changed()

    def on_textentry_frequency_key_press(self, widget, event):
        if event.keyval == 65293: # user pressed enter
            self.on_frequency_changed()

    def on_frequency_changed(self):
        frequency = self.textentry_frequency.get_text()
        if isfloat(frequency):
            self.app.set_frequency(float(frequency)*1e3)
        else:
            print "error" # TODO dialog error
            self.textentry_frequency.set_text(str(self.app.protocol.current_step().frequency/1e3))

    def on_measure_impedance_toggled(self, widget, data=None):
        if self.checkbutton_measure_impedance.get_active():
            self.app.protocol.current_step().measure_impedance = \
                MeasureImpedance()
        else:
            self.app.protocol.current_step().measure_impedance = None

    def on_run_protocol(self, widget, data=None):
        self.on_first_step()
        self.data = []
        for i in range(0, 4):
            self.data.append(range(i+10,i+0,-1))
        plt.figure()
        self.run_step()

    def run_step(self):
        self.app.main_window_controller.update()
        if self.app.protocol.current_step_number < len(self.app.protocol)-1:
            measure_impedance = self.app.protocol.current_step().measure_impedance
            state = self.app.protocol.current_step().state_of_electrodes
            if measure_impedance:
                impedance = self.app.controller.MeasureImpedance(
                                                measure_impedance.sampling_time_ms,
                                                measure_impedance.n_sets,
                                                measure_impedance.delay_between_sets_ms,
                                                state)
                #self.data.append(impedance)
                self.app.protocol.next_step()
                self.run_step()
            else:
                self.app.controller.set_state_of_all_electrodes(state)
                self.app.protocol.next_step()
                self.timer_id = gobject.timeout_add(self.app.protocol.current_step().time,
                                                    self.run_step)
        else:
            legend_str = []
            i = 0
            for d in self.data:
                plt.plot(d)
                legend_str.append("electrode %d" % i)
                i+=1
            plt.xlabel("time (ms)")
            plt.ylabel("Impedance ($\Omega$)")
            plt.legend(legend_str)
            plt.show()
        return False

    def update(self):
        self.textentry_step_time.set_text(str(self.app.protocol.current_step().time))
        self.textentry_voltage.set_text(str(self.app.protocol.current_step().voltage))
        self.textentry_frequency.set_text(str(self.app.protocol.current_step().frequency/1e3))
        self.label_step_number.set_text("Step: %d/%d" % 
            (self.app.protocol.current_step_number+1, len(self.app.protocol.steps)))
        if self.app.protocol.current_step().measure_impedance:
            self.checkbutton_measure_impedance.set_active(True)
        else:
            self.checkbutton_measure_impedance.set_active(False)