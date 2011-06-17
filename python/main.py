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

    def state_of_all_electrodes(self):
        if self.realtime_mode:
            state = self.controller.state_of_all_electrodes()
        else:
            state = self.protocol.current_step().state_of_all_electrodes()
        return state

    def set_state_of_all_electrodes(self, state):
        if self.realtime_mode:
            self.controller.set_state_of_all_electrodes(state)
        else:
            self.protocol.current_step().set_state_of_all_electrodes(state)

    def toggle_realtime_mode(self):
        if self.realtime_mode:
            self.realtime_mode = False
        else:
            self.realtime_mode = True

if __name__ == '__main__':
    app = App()
