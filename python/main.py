from gui.main_window import MainWindow
from controllers.dmf_controller import DmfController
from protocol import Protocol

class App:
    def __init__(self):
        self.realtime_mode = False
        self.controller = DmfController()
        self.func_gen = None
        self.protocol = Protocol()
        self.main_window = MainWindow(self)
        self.main_window.main()

    def state_of_all_electrodes(self):
        if self.realtime_mode:
            state = self.controller.state_of_all_electrodes()
        else:
            state = self.protocol.state_of_all_electrodes()
        return state

    def set_state_of_electrode(self, index, state):
        if self.realtime_mode:
            self.controller.set_state_of_electrode(int(index), state)
        else:
            self.protocol.set_state_of_electrode(index, state)

    def set_voltage(self, voltage):
        if self.realtime_mode:
            self.controller.set_voltage(voltage)
        else:
            self.protocol.current_step().voltage = voltage

    def set_frequency(self, frequency):
        if self.realtime_mode:
            self.controller.set_freuqency(frequency)
        else:
            self.protocol.current_step().frequency = frequency

if __name__ == '__main__':
    app = App()
