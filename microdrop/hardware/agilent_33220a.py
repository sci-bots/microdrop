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

import time
try:
    import visa
except:
    pass

class Agilent33220A():
    def __init__(self):
        self.connected = False
        self.idn = ""
        try:
            instrument_list = visa.get_instruments_list()[0]
        except:
            return

        if instrument_list:
            try:
                self.instrument = visa.instrument(instrument_list)
            except:
                return

            try:
                self.idn = self.instrument.ask("*IDN?")
                self.connected = True
            except:
                self.idn = ""
                self.instrument.close()
                return
        
            self.instrument.write("*RST") # reset the function generator
            self.instrument.write("*CLS") # clear errors and status registers
            self.instrument.write("FUNC SIN") # select waveshape
            self.instrument.write("OUTP:LOAD 50") # set the load impedance in Ohms
            self.instrument.write("FREQ 1e3") # set the frequency to 1 kHz
            self.instrument.write("VOLT 0.01") # set the voltage to 1 Vpp
            self.instrument.write("OUTP ON") # turn on the output
            
    def __repr__(self):
        return self.idn
    
    def is_connected(self):
        return self.connected

    def set_waveform(self, waveform):
        if waveform == "SINE":
            self.instrument.write("FUNC SIN")
        elif waveform == "SQUARE":
            self.instrument.write("FUNC SIN")
        else:
            raise Exception("Unsupported waveform")
        
    def set_voltage(self, voltage):
        self.instrument.write("VOLT %f" % voltage)
        time.sleep(.01) # need to allow ~10 ms for instrument to update
        
    def voltage(self):
        return float(self.instrument.ask("VOLT?"))
    
    def set_frequency(self, frequency):
        self.instrument.write("FREQ %f" % frequency)
        time.sleep(.01) # need to allow ~10 ms for instrument to update
        
    def frequency(self):
        return float(self.instrument.ask("FREQ?"))