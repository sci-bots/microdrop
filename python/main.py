import os, gtk, time
from hardware.dmf_control_board import DmfControlBoard
from hardware.agilent_33220a import Agilent33220A
from gui.main_window_controller import MainWindowController
from gui.device_controller import DeviceController
from gui.protocol_controller import ProtocolController
import protocol
from experiment_log import ExperimentLog

class App:
    def __init__(self):
        self.realtime_mode = False
        self.is_running = False
        
        self.control_board = DmfControlBoard()
        #self.control_board.set_debug(True)
        self.func_gen = Agilent33220A()
        self.protocol = protocol.Protocol()
        self.experiment_log = ExperimentLog()
        self.builder = gtk.Builder()

        signals = {}
        self.main_window_controller = MainWindowController(self, self.builder, signals)
        self.device_controller = DeviceController(self, self.builder, signals)
        self.protocol_controller = ProtocolController(self, self.builder, signals)
        self.builder.connect_signals(signals)
        self.main_window_controller.main()

    def load_protocol(self, filename):
        self.protocol = protocol.load(filename)

    def run_protocol(self):
        self.is_running = True
        self.run_step()

    def pause_protocol(self):
        self.is_running = False
        
    def run_step(self):
        self.main_window_controller.update()
        if self.control_board.connected():
            feedback_options = \
                self.protocol.current_step().feedback_options
            state = self.protocol.current_step().state_of_channels
            if feedback_options: # run this step with feedback
                ad_channel = 1
                
                data = {"step":self.protocol.current_step_number,
                        "time":time.time()}

                # measure droplet impedance
                self.control_board.set_series_resistor(ad_channel, 2)
                impedance = self.control_board.MeasureImpedance(
                           feedback_options.sampling_time_ms,
                           feedback_options.n_samples,
                           feedback_options.delay_between_samples_ms,
                           state)
                data["impedance"] = impedance
                
                # measure the voltage waveform for each series resistor
                for i in range(0,4):
                    self.control_board.set_series_resistor(ad_channel,i)
                    voltage_waveform = self.control_board.SampleVoltage(
                                [ad_channel], 1000, ad_channel, 0, state)
                    data["voltage waveform (SR=%d k)" %
                         self.control_board.series_resistor(ad_channel)] = \
                         voltage_waveform

                self.experiment_log.add_data(data)
            else:   # run without feedback
                self.control_board.set_state_of_all_channels(state)
                time.sleep(self.protocol.current_step().time/1000.0)
        else: # run through protocol (even though device is not connected)
                time.sleep(self.protocol.current_step().time/1000.0)

        if self.protocol.current_step_number < len(self.protocol)-1:
            self.protocol.next_step()
        else: # we're on the last step
            self.is_running = False
            # save the experiment protocol and log
            log_path = self.experiment_log.get_path()
            self.protocol.save(os.path.join(log_path,"protocol"))
            self.experiment_log.save()
            self.experiment_log.plot()
            self.experiment_log.clear()
            self.main_window_controller.update()

        if self.is_running:
            self.run_step()
        
if __name__ == '__main__':
    app = App()