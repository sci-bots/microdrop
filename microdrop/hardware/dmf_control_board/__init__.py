"""
Copyright 2011 Ryan Fobel and Christian Fobel

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

from dmf_control_board_base import DmfControlBoard as Base
from dmf_control_board_base import uint8_tVector, INPUT, OUTPUT, HIGH, LOW, SINE, SQUARE
from avr.serial_device import SerialDevice, ConnectionError
from utility import is_float

import numpy

class DmfControlBoard(Base, SerialDevice):
    def state_of_all_channels(self):
        return numpy.array(Base.state_of_all_channels(self))

    def set_state_of_all_channels(self, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        return Base.set_state_of_all_channels(self, state_)

    def default_pin_modes(self):
        pin_modes = []
        for i in range(0,53/8+1):
            mode = self.eeprom_read(self.EEPROM_PIN_MODE_ADDRESS+i)
            for j in range(0,8):
                if i*8+j<=53:
                    pin_modes.append(~mode>>j&0x01)
        return pin_modes
        
    def set_default_pin_modes(self, pin_modes):
        for i in range(0,53/8+1):
            mode = 0
            for j in range(0,8):
                if i*8+j<=53:
                    mode += pin_modes[i*8+j]<<j
            self.eeprom_write(self.EEPROM_PIN_MODE_ADDRESS+i,~mode&0xFF)
            
    def default_pin_states(self):
        pin_states = []
        for i in range(0,53/8+1):
            state = self.eeprom_read(self.EEPROM_PIN_STATE_ADDRESS+i)
            for j in range(0,8):
                if i*8+j<=53:
                    pin_states.append(~state>>j&0x01)
        return pin_states
        
    def set_default_pin_states(self, pin_states):
        for i in range(0,53/8+1):
            state = 0
            for j in range(0,8):
                if i*8+j<=53:
                    state += pin_states[i*8+j]<<j
            self.eeprom_write(self.EEPROM_PIN_STATE_ADDRESS+i,~state&0xFF)

    def sample_voltage(self, ad_channel, n_samples, n_sets,
                       delay_between_sets_ms, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        ad_channel_ = uint8_tVector()
        for i in range(0, len(ad_channel)):
            ad_channel_.append(int(ad_channel[i]))
        return numpy.array(Base.sample_voltage(self,
                                ad_channel_, n_samples, n_sets,
                                delay_between_sets_ms,
                                state_))
    
    def measure_impedance(self, sampling_time_ms, n_samples,
                          delay_between_samples_ms, state):
        state_ = uint8_tVector()
        for i in range(0, len(state)):
            state_.append(int(state[i]))
        return numpy.array(Base.measure_impedance(self,
                                sampling_time_ms, n_samples,
                                delay_between_samples_ms, state_))
        
    def i2c_write(self, address, data):
        data_ = uint8_tVector()
        for i in range(0, len(data)):
            data_.append(int(data[i]))
        Base.i2c_write(self, address, data_)
        

class DmfControlBoardInfo(SerialDevice):
    def __init__(self):
        self.port = None
        try:
            from hardware.dmf_control_board import DmfControlBoard
        except ImportError:
            raise
        else:
            self.control_board = DmfControlBoard()

        self.port = self.get_port()

        if not self.control_board.connected():
            del self.control_board
            raise ConnectionError('Could not connect to device.')
        else:
            self.firmware_version = self.control_board.software_version()
            self.driver_version = self.control_board.host_software_version()
            del self.control_board


    def test_connection(self, port):
        from hardware.dmf_control_board import DmfControlBoard

        try:
            if self.control_board.connect(port) == DmfControlBoard.RETURN_OK:
                self.port = port
                self.control_board.flush()
                name = self.control_board.name()
                version = 0
                if is_float(self.control_board.hardware_version()):
                    version = float(self.control_board.hardware_version())
                if name == "Arduino DMF Controller" and version >= 1.1:
                    return True
        except:
            pass
        return False