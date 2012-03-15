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
from path import path
import yaml

from utility import base_path, PROGRAM_LAUNCHED
from dmf_device import DmfDevice
from protocol import Protocol
from config import Config
from experiment_log import ExperimentLog
from plugin_manager import PluginManager, SingletonPlugin, ExtensionPoint, \
    IPlugin, implements, PluginGlobals, Plugin
from plugin_helpers import AppDataController
from logger import logger, CustomHandler, logging
from app_context import plugin_manager
from gui.plugin_manager_dialog import PluginManagerDialog


PluginGlobals.push_env('microdrop')
    

# these imports automatically load (and initialize) core singleton plugins
import gui.experiment_log_controller
import gui.config_controller
import gui.main_window_controller
import gui.dmf_device_controller
import gui.protocol_controller
import gui.protocol_grid_controller
import gui.video_controller
import gui.app_options_controller


class App(Plugin):
    implements(IPlugin)
    '''
INFO:  <Plugin App 'microdrop.app'>
INFO:  <Plugin ConfigController 'microdrop.gui.config_controller'>
INFO:  <Plugin DmfControlBoardPlugin 'wheelerlab.dmf_control_board_1.2'>
INFO:  <Plugin DmfDeviceController 'microdrop.gui.dmf_device_controller'>
INFO:  <Plugin ExperimentLogController 'microdrop.gui.experiment_log_controller'>
INFO:  <Plugin MainWindowController 'microdrop.gui.main_window_controller'>
INFO:  <Plugin ProtocolController 'microdrop.gui.protocol_controller'>
INFO:  <Plugin ProtocolGridController 'microdrop.gui.protocol_grid_controller'>
INFO:  <Plugin VideoController 'microdrop.gui.video_controller'>
    '''
    core_plugins = ['microdrop.app',
            'microdrop.gui.config_controller',
            'microdrop.gui.dmf_device_controller',
            'microdrop.gui.experiment_log_controller',
            'microdrop.gui.main_window_controller',
            'microdrop.gui.protocol_controller',
            'microdrop.gui.protocol_grid_controller',
            'microdrop.gui.video_controller',]

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
        self.plugin_data = {}

        # these members are initialized by plugins
        self.control_board = None
        self.experiment_log_controller = None
        self.config_controller = None
        self.dmf_device_controller = None 
        self.protocol_controller = None
        self.main_window_controller = None

        # Enable custom logging handler
        logger.addHandler(CustomHandler())
        self.log_file_handler = None

        # config model
        self.config = Config()

        # Delete paths that were marked during the uninstallation of a plugin.
        # It is necessary to delay the deletion until here due to Windows file
        # locking preventing the deletion of files that are in use.
        deletions_path = path(self.config.data['plugins']['directory'])\
                .joinpath('requested_deletions.yml')
        if deletions_path.isfile():
            requested_deletions = yaml.load(deletions_path.bytes())
            requested_deletions = map(path, requested_deletions)
            logger.info('[App] processing requested deletions.')
            for p in requested_deletions:
                try:
                    if p != p.abspath():
                        logger.info('    (warning) ignoring path %s since it is '\
                                'not absolute' % p)
                        continue
                    if p.isdir():
                        # Test to make sure this looks like a plugin
                        if p.joinpath('microdrop').isdir():
                            plugin_root = p
                        elif len(p.dirs()) == 1:
                            plugin_root = path(p.dirs()[0])
                        info = PluginManagerDialog.get_plugin_info(plugin_root)
                        if info:
                            logger.info('  deleting %s' % p)
                            cwd = os.getcwd()
                            os.chdir(p.parent)
                            try:
                                path(p.name).rmtree() #ignore_errors=True)
                            except Exception, why:
                                logger.warning('Error deleting path %s (%s)'\
                                        % (p, why))
                                raise
                            os.chdir(cwd)
                            requested_deletions.remove(p)
                except (AssertionError,):
                    logger.info('  NOT deleting %s info=%s' % (p, info))
                    continue
            deletions_path.write_bytes(yaml.dump(requested_deletions))

        # dmf device
        self.dmf_device = DmfDevice()

        # protocol
        self.protocol = Protocol()

    def get_data(self, plugin_name):
        logging.debug('[App] plugin_data=%s' % self.plugin_data)
        data = self.plugin_data.get(plugin_name)
        if data:
            return data
        else:
            return {}
    
    def set_data(self, plugin_name, data):
        self.plugin_data[plugin_name] = data

    def on_protocol_changed(self, protocol):
        self.protocol = protocol

    @property
    def plugins(self):
        return set(self.plugin_data.keys())

    def plugin_name_lookup(self, name, re_pattern=False):
        if not re_pattern:
            return name

        for plugin_name in self.plugins:
            if re.search(name, plugin_name):
                return plugin_name
        return None

    def run(self):
        plugin_manager.load_plugins(self.config['plugins']['directory'])

        plugin_manager.emit_signal('on_app_init')
        self.update_log_file()
                
        self.builder.connect_signals(self.signals)

        # Load optional plugins marked as enabled in config
        for p in self.config['plugins']['enabled']:
            try:
                plugin_manager.enable(p)
            except KeyError:
                logger.warning('Requested plugin (%s) is not available.\n\n'
                    'Please check that it exists in the plugins '
                    'directory:\n\n    %s' % (p, self.config['plugins']['directory']))
        plugin_manager.log_summary()

        # experiment logs
        device_path = None
        if self.dmf_device.name:
            directory = self.get_device_directory()
            if directory:
                device_path = os.path.join(directory,
                        self.dmf_device.name, "logs")
        self.experiment_log = ExperimentLog(device_path)

        # save the protocol name from the config file because it is
        # automatically overwritten when we load a new device
        protocol_name = self.config['protocol']['name']

        # load the device from the config file
        if self.config['dmf_device']['name']:
            directory = self.get_device_directory()
            if directory:
                device_path = os.path.join(directory,
                                           self.config['dmf_device']['name'],
                                           'device')
                self.dmf_device_controller.load_device(device_path)

            # reapply the protocol name to the config file
            self.config['protocol']['name'] = protocol_name
    
            # load the protocol
            if self.config['protocol']['name']:
                directory = self.get_device_directory()
                if directory:
                    filename = os.path.join(directory,
                                            self.config['dmf_device']['name'],
                                            "protocols",
                                            self.config['protocol']['name'])
                    self.protocol_controller.load_protocol(filename)
        
        self.main_window_controller.main()

    def _set_log_file_handler(self, log_file):
        if self.log_file_handler:
            self._destroy_log_file_handler()
        self.log_file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        self.log_file_handler.setFormatter(formatter)
        logger.addHandler(self.log_file_handler)
        logger.info('[App] added log_file_handler: %s' % log_file)

    def _destroy_log_file_handler(self):
        if self.log_file_handler is None:
            return
        logger.info('[App] closing log_file_handler')
        self.log_file_handler.close()
        del self.log_file_handler
        self.log_file_handler = None

    def update_log_file(self):
        plugin_name = 'microdrop.gui.main_window_controller'
        values = AppDataController.get_plugin_app_values(plugin_name)
        logger.debug('[App] update_log_file %s' % values)
        required = set(['log_enabled', 'log_file'])
        if values is None or required.intersection(values.keys()) != required:
            return
        # values contains both log_enabled and log_file
        log_file = values['log_file']
        log_enabled = values['log_enabled']
        if self.log_file_handler is None:
            if log_enabled:
                self._set_log_file_handler(log_file)
                logger.info('[App] logging enabled')
        else:
            # Log file handler already exists
            if log_enabled:
                if log_file != self.log_file_handler.baseFilename:
                    # Requested log file path has been changed
                    self._set_log_file_handler(log_file)
            else:
                self._destroy_log_file_handler()

    def on_dmf_device_changed(self, dmf_device):
        self.dmf_device = dmf_device
    
    def on_protocol_changed(self, protocol):
        self.protocol = protocol
    
    def on_experiment_log_changed(self, experiment_log):
        self.experiment_log = experiment_log

    def get_device_directory(self):
        observers = ExtensionPoint(IPlugin)
        plugin_name = 'microdrop.gui.dmf_device_controller'
        service = observers.service(plugin_name)
        values = service.get_app_values()
        if values and 'device_directory' in values:
            directory = path(values['device_directory'])
            if directory.isdir():
                return directory
        return None


PluginGlobals.pop_env()


if __name__ == '__main__':
    os.chdir(base_path())
