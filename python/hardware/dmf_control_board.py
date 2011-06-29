from dmf_control_board_base import DmfControlBoard as Base
from dmf_control_board_base import uint8_tVector

import numpy

class DmfControlBoard(Base):
    def state_of_all_channels(self):
        return numpy.array(Base.state_of_all_channels(self))

    def set_state_of_all_channels(self, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        return Base.set_state_of_all_channels(self, state_)

    def MeasureImpedance(self, sampling_time_ms, n_sets,
                         delay_between_sets_ms, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        return numpy.array(Base.MeasureImpedance(self,
                                    sampling_time_ms, n_sets,
                                    delay_between_sets_ms, state_))