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
import subprocess
import re
import traceback

import gtk
import numpy as np

from utility import base_path, PROGRAM_LAUNCHED
from dmf_device import DmfDevice
from protocol import Protocol
from config import load as load_config
from experiment_log import ExperimentLog
from plugin_manager import PluginManager, SingletonPlugin, ExtensionPoint, \
    IPlugin, implements, PluginGlobals
from logger import logger, CustomHandler


PluginGlobals.push_env('microdrop')
    

# these imports automatically load (and initialize) core singleton plugins
import gui.experiment_log_controller
import gui.config_controller
import gui.main_window_controller
import gui.dmf_device_controller
import gui.protocol_controller


class App(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.app"
        # get the version number
        self.version = ""
        try:
            version = subprocess.Popen(['git','describe'],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          stdin=subprocess.PIPE).communicate()[0].rstrip()
            m = re.match('v(\d+)\.(\d+)-(\d+)', version)
            self.version = "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
        except:
            if os.path.isfile('version.txt'):
                try:
                    f = open('version.txt', 'r')
                    self.version = f.readline().strip()
                finally:
                    f.close()
            
        self.realtime_mode = False
        self.running = False
        self.builder = gtk.Builder()
        self.signals = {}

        # these members are initialized by plugins
        self.control_board = None
        self.experiment_log_controller = None
        self.config_controller = None
        self.dmf_device_controller = None 
        self.protocol_controller = None
        self.main_window_controller = None

        # load plugins
        self.plugin_manager = PluginManager()

        # Enable custom logging handler
        logger.addHandler(CustomHandler())

        # config model
        self.config = load_config()
        
        # dmf device
        self.dmf_device = DmfDevice()

        # protocol
        self.protocol = Protocol()

        # Initialize main window controller and dmf device
        # controller first (necessary for other plugins to add items to the
        # menus, etc.)
        observers = ExtensionPoint(IPlugin)
        preinit_plugins = ['microdrop.gui.main_window_controller',
                                    'microdrop.gui.dmf_device_controller']
        for plugin in preinit_plugins:
            observers(plugin)[0].on_app_init(self)
        
        # initialize other plugins
        for observer in observers:
            if observer.name not in preinit_plugins and \
                hasattr(observer,"on_app_init"):
                logger.info("Initialize %s plugin" % observer.name)
                try:
                    observer.on_app_init(self)
                except Exception, why:
                    logger.error(str(why))
                    logger.error(''.join(traceback.format_stack()))
                
        self.builder.connect_signals(self.signals)

        # process the config file
        self.config_controller.process_config_file()
        
        # Load optional plugins marked as enabled in config
        for p in self.config.enabled_plugins:
            self.plugin_manager.enable(self, p)
        self.plugin_manager.log_summary()

        # experiment logs
        device_path = None
        if self.dmf_device.name:
            device_path = os.path.join(self.config.dmf_device_directory,
                                       self.dmf_device.name, "logs")
        self.experiment_log = ExperimentLog(device_path)
        
        self.main_window_controller.main()

    def on_dmf_device_changed(self, dmf_device):
        self.dmf_device = dmf_device

    def on_protocol_changed(self, protocol):
        self.protocol = protocol

    def on_experiment_log_changed(self, experiment_log):
        self.experiment_log = experiment_log
        

PluginGlobals.pop_env()


if __name__ == '__main__':
    os.chdir(base_path())
