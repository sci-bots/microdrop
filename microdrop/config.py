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
from shutil import ignore_patterns

from path import path

from logger import logger, logging
from utility.user_paths import home_dir, app_data_dir, common_app_data_dir


def get_skeleton_path(dir_name):
    if os.name == 'nt':
        source_dir = common_app_data_dir().joinpath('Microdrop', dir_name)
        if not source_dir.isdir():
            logger.warning('warning: %s does not exist in common AppData dir'\
                            % dir_name)
            source_dir = path(dir_name)
    else:
        source_dir = path(dir_name)
    if not source_dir.isdir():
        raise IOError, '%s/ directory not available.' % source_dir
    return source_dir


def device_skeleton_path():
    return get_skeleton_path('devices')


def plugins_skeleton_path():
    return get_skeleton_path('plugins')


def load(filename=None):
    if filename is None:
        filename = Config.filename
    if os.path.isfile(filename):
        f = open(filename, 'rb')
        config = pickle.load(f)
        f.close()
    else:
        config = Config()
    if config.upgrade():
        config.save()
    return config


class LogFileConfig(object):
    class_version = '0.1'

    def __init__(self, log_file=None, file_enabled=False,
                    level=logging.DEBUG):
        self.file = log_file
        self.enabled = file_enabled
        self._level = level
        self.version = self.class_version

    def __repr__(self):
        return '''LogFileConfig(%s, %s, %s)''' % (self._file,
                            self._enabled, self._level)

    def upgrade(self):
        upgraded = False
        if not hasattr(self, 'version'):
            self.version = '0.0'
        version = float(self.version)
        logger.info('[LogFileConfig] upgrade from version %s' % self.version)
        if version < 0.1:
            self.version = '0.1'
            self.file = self._file
            self.enabled = self._enabled
            self.level = self._level
            logger.info('[LogFileConfig] upgrade to version 0.1')
            upgraded = True
        return upgraded


class Config():
    class_version = '0.11'
    filename = app_data_dir().joinpath('.microdroprc')
    
    def __init__(self):
        self.version = self.class_version
        
        self.init_devices_dir()
        self.init_plugins_dir()
        self.dmf_device_name = None
        self.protocol_name = None
        self.enabled_plugins = []

        # Added in version 0.1
        self.log_file_config = LogFileConfig()

    def init_devices_dir(self):
        if os.name == 'nt':
            self.dmf_device_directory = home_dir().joinpath('Microdrop', 'devices')
        else:
            self.dmf_device_directory = home_dir().joinpath('.microdrop', 'devices')
        self.dmf_device_directory.parent.makedirs_p()
        devices = device_skeleton_path()
        if not self.dmf_device_directory.isdir():
            devices.copytree(self.dmf_device_directory)

    def init_plugins_dir(self):
        if os.name == 'nt':
            self.plugins_directory = home_dir().joinpath('Microdrop', 'plugins')
        else:
            self.plugins_directory = home_dir().joinpath('.microdrop', 'plugins')
        self.plugins_directory.parent.makedirs_p()
        plugins = plugins_skeleton_path()
        if not self.plugins_directory.isdir():
            # Copy plugins directory to app data directory, keeping symlinks
            # intact.  If we don't keep symlinks as they are, we might end up
            # with infinite recursion.
            plugins.copytree(self.plugins_directory, symlinks=True,
                ignore=ignore_patterns('*.pyc'))

    def set_plugins(self, plugins):
        self.enabled_plugins = plugins

    def get_data_dir(self):
        return self.dmf_device_directory.parent
        
    def upgrade(self):
        upgraded = False
        if not hasattr(self, 'version'):
            self.version = '0.0'
        version = float(self.version)
        logger.info('upgrade from version %s' % self.version)
        if version < 0.1:
            self.version = '0.1'
            self.enabled_plugins = []
            self.log_file_config = LogFileConfig()
            logger.info('upgrade to version 0.1')
            upgraded = True
        if version < 0.11:
            self.version = '0.11'
            self.init_plugins_dir()
            print '[Config] self.plugins_directory = %s' % self.plugins_directory
            logger.info('upgrade to version 0.11')
            upgraded = True
        self.log_file_config.upgrade()
        return upgraded

    def save(self, filename=None):
        if filename == None:
            filename = Config.filename
        f = open(filename, 'wb')
        pickle.dump(self, f, -1)
        f.close()
