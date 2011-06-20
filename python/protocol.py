import sys
import numpy as np
from controllers.dmf_controller import DmfController
from controllers.agilent_33220a import Agilent33220A

class Step():
    def __init__(self, n_electrodes, time=None):
        if time:
            self.time = time
        else:
            self.time = 100
        self.n_electrodes = n_electrodes
        self.state_of_electrodes = np.zeros(n_electrodes)

class Protocol():
    def __init__(self, n_electrodes=None):
        if n_electrodes:
            self.n_electrodes = n_electrodes
        else:
            self.n_electrodes = 40
        self.current_step_number = 0
        self.steps = [Step(self.n_electrodes)]

    def __len__(self):
        return len(self.steps)

    def set_state_of_electrode(self, index, state):
        self.current_step().state_of_electrodes[index] = state

    def state_of_all_electrodes(self):
        return self.current_step().state_of_electrodes

    def current_step(self):
        return self.steps[self.current_step_number]

    def insert_step(self):
        self.steps.insert(self.current_step_number, Step(self.n_electrodes))

    def delete_step(self):
        if len(self.steps) > 1:
            del self.steps[self.current_step_number]
            if self.current_step_number == len(self.steps):
                self.current_step_number -= 1
        else: # reset first step
            self.steps = [Step(self.n_electrodes)]

    def next_step(self):
        if self.current_step_number == len(self.steps)-1:
            self.steps.append(Step(self.n_electrodes))
        self.goto_step(self.current_step_number+1)
            
    def prev_step(self):
        if self.current_step_number > 0:
            self.goto_step(self.current_step_number-1)

    def first_step(self):
        self.goto_step(0)

    def last_step(self):
        self.goto_step(len(self.steps)-1)

    def goto_step(self, step):
        self.current_step_number = step
