from dmf_controller_base import DmfController as Base
from dmf_controller_base import uint8_tVector

import numpy

class DmfController(Base):
    def state_of_all_electrodes(self):
        return numpy.array(Base.state_of_all_electrodes(self))

    def set_state_of_all_electrodes(self, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        Base.set_state_of_all_electrodes(self, state_)

    def MeasureImpedance(self, sampling_time_ms, n_sets,
                         delay_between_sets_ms, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        return numpy.array(Base.MeasureImpedance(self,
                                    sampling_time_ms, n_sets,
                                    delay_between_sets_ms, state_))
