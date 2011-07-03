import visa, time

class Agilent33220A():
    def __init__(self):
        self.instrument = visa.instrument(visa.get_instruments_list()[0])
        self.instrument.write("*RST") # reset the function generator
        self.instrument.write("*CLS") # clear errors and status registers
        self.instrument.write("FUNC SIN") # select waveshape
        self.instrument.write("OUTP:LOAD 50") # set the load impedance in Ohms
        self.instrument.write("FREQ 1e3") # set the frequency to 1 kHz
        self.instrument.write("VOLT 0.01") # set the voltage to 1 Vpp
        self.instrument.write("OUTP ON") # turn on the output
    def __repr__(self):
        return self.instrument.ask("*IDN?")
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
