"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import gtk
import subprocess
import re
import numpy as np

from utility import base_path
from hardware.dmf_control_board.device import DmfControlBoard
from hardware.agilent_33220a import Agilent33220A
from gui.main_window_controller import MainWindowController
from gui.dmf_device_controller import DmfDeviceController
from gui.protocol_controller import ProtocolController
from gui.config_controller import ConfigController
from gui.experiment_log_controller import ExperimentLogController
from config import load as load_config
from experiment_log import ExperimentLog
from plugin_manager import PluginManager, ExtensionPoint, IPlugin
    
class App:
    observers = ExtensionPoint(IPlugin)
        
    def __init__(self):
        # get the version number
        self.version = ""
        try:
            version = subprocess.Popen(['git','describe'],
                          stdout=subprocess.PIPE).communicate()[0].rstrip()
            m = re.match('v(\d+)\.(\d+)-(\d+)', version)
            self.version = "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
        except:
            pass
            
        self.realtime_mode = False
        self.running = False
        self.builder = gtk.Builder()
        signals = {}

        # function generator
        self.func_gen = Agilent33220A()
       
        # control board
        self.control_board = DmfControlBoard()
        #self.control_board.set_debug(True)
        
        # load plugins
        self.plugin_manager = PluginManager()

        # main window
        self.main_window_controller = MainWindowController(self, self.builder,
                                                           signals)

        # config model and controller
        self.config = load_config()
        self.config_controller = ConfigController(self)
        
        # dmf device
        self.dmf_device = self.config_controller.load_dmf_device()
        self.dmf_device_controller = DmfDeviceController(self, self.builder,
                                                         signals)
        # protocol
        self.protocol = self.config_controller.load_protocol()
        self.protocol_controller = ProtocolController(self, self.builder,
                                                      signals)
        
        # experiment logs
        device_path = None
        if self.dmf_device.name:
            device_path = os.path.join(self.config.dmf_device_directory,
                                       self.dmf_device.name, "logs")
        self.experiment_log = ExperimentLog(device_path)
        self.experiment_log_controller = ExperimentLogController(self)
        
        for observer in self.observers:
            if hasattr(observer,"on_app_init"):
                observer.on_app_init(self)

        self.builder.connect_signals(signals)
        self.main_window_controller.main()
        
if __name__ == '__main__':
    os.chdir(base_path())
    app = App()
