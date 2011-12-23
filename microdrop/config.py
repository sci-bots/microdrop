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

import os
try:
    import cPickle as pickle
except ImportError:
    import pickle

from path import path

from logger import logger
from utility.user_paths import home_dir, app_data_dir, common_app_data_dir


def device_skeleton_path():
    if os.name == 'nt':
        devices = common_app_data_dir().joinpath('Microdrop', 'devices')
        if not devices.isdir():
            logger.warning('warning: devices does not exist in common AppData dir')
            devices = path('devices')
    else:
        devices = path('devices')
    if not devices.isdir():
        raise IOError, 'devices/ directory not available.'
    return devices


def load(filename=None):
    if filename is None:
        filename = Config.filename
    if os.path.isfile(filename):
        f = open(filename, 'rb')
        config = pickle.load(f)
        f.close()
    else:
        config = Config()
    return config


class Config():
    filename = app_data_dir().joinpath('.microdroprc')
    
    def __init__(self):
        if os.name == 'nt':
            self.dmf_device_directory = home_dir().joinpath('Microdrop', 'devices')
        else:
            self.dmf_device_directory = home_dir().joinpath('.microdrop', 'devices')
        self.dmf_device_directory.parent.makedirs_p()
        devices = device_skeleton_path()
        if not self.dmf_device_directory.isdir():
            devices.copytree(self.dmf_device_directory)

        self.dmf_device_name = None
        self.protocol_name = None
        self.enabled_plugins = []

    def set_plugins(self, plugins):
        self.enabled_plugins = plugins

    def get_data_dir(self):
        return self.dmf_device_directory.parent
        
    def save(self, filename=None):
        if filename == None:
            filename = Config.filename
        f = open(filename, 'wb')
        pickle.dump(self, f, -1)
        f.close()
