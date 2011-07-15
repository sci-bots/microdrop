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

import os, cPickle
from dmf_device import DmfDevice, load as load_dmf_device
from protocol import Protocol, load as load_protocol

def load(filename=None):
    if filename is None:
        filename = Config.filename
    if os.path.isfile(filename):
        f = open(filename, 'rb')
        config = cPickle.load(f)
        f.close()
    else:
        config = Config()
    return config

class Config():
    filename = ".microdrop"
    
    def __init__(self):
        self.dmf_device_directory = "devices"
        self.dmf_device_name = None
        self.protocol_name = None
        
    def save(self, filename=None):
        if filename == None:
            filename = Config.filename
        f = open(filename, 'wb')
        cPickle.dump(self, f, -1)
        f.close()
        
    def load_dmf_device(self):
        # try what's specified in config file
        if self.dmf_device_name:
            try:
                path = os.path.join(self.dmf_device_directory,
                                    self.dmf_device_name,
                                    "device")
                return load_dmf_device(path)
            except:
                pass
                #raise Exception("Error loading DMF device")

        # otherwise, return a new object
        return DmfDevice()
    
    def load_protocol(self):
        # try what's specified in config file
        if self.protocol_name:
            try:
                path = os.path.join(self.dmf_device_directory,
                                    self.dmf_device_name,
                                    "protocols",
                                    self.protocol_name)
                return load_protocol(path)
            except:
                pass
                #raise Exception("Error loading protocol")

        # otherwise, return a new object
        return Protocol()