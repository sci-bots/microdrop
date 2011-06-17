import numpy as np
from controllers.dmf_controller import DmfController
from controllers.agilent_33220a import Agilent33220A

class Step():
    def __init__(self, protocol):
        self.protocol = protocol
        self.state_of_electrodes = np.zeros(protocol.n_electrodes)
        self.on = []
        self.off = []
        self.time = 100

    def state_of_all_electrodes(self):
        return self.state_of_electrodes

    def set_state_of_all_electrodes(self, state):
        self.state_of_electrodes = state

class Protocol():
    def __init__(self, n_electrodes=None):
        if n_electrodes:
            self.n_electrodes = n_electrodes
        else:
            self.n_electrodes = 40
        self.steps = [Step(self)]
        self.current_step_number = 0

    def current_step(self):
        return self.steps[self.current_step_number]

    def insert_step(self):
        pass

    def __len__(self):
        len(steps)

    def next_step(self):
        pass

    def prev_step(self):
        pass

    def first_step(self):
        pass

    def last_step(self):
        pass
