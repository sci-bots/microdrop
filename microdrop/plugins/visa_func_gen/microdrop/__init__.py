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

from plugins.visa_func_gen import *
from plugin_manager import IWaveformGenerator, SingletonPlugin, implements

class VisaFuncGenPlugin(SingletonPlugin):
    implements(IWaveformGenerator)
    
    def __init__(self):
        self.func_gen = VisaFuncGen()
    
    def set_voltage(self, voltage):
        """
        Set the waveform voltage.
        
        Parameters:
            voltage : RMS voltage
        """
        if self.func_gen.is_connected():
            self.func_gen.set_voltage(voltage)
    
    def set_frequency(self, frequency):
        """
        Set the waveform frequency.
        
        Parameters:
            frequency : frequency in Hz
        """
        if self.func_gen.is_connected():
            self.func_gen.set_frequency(frequency)