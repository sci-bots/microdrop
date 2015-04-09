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
from shutil import ignore_patterns
import warnings

from path_helpers import path
from configobj import ConfigObj, Section, flatten_errors
from validate import Validator
from microdrop_utility.user_paths import (home_dir, app_data_dir,
                                          common_app_data_dir)

from .logger import logger
from . import base_path


class ValidationError(Exception):
    pass


class Config(object):
    if os.name == 'nt':
        default_config_directory = home_dir().joinpath('Microdrop')
    else:
        default_config_directory = app_data_dir().joinpath('.microdrop')
    default_config_path = default_config_directory / path('microdrop.ini')
    spec = """
        [dmf_device]
        # name of the most recently used DMF device
        name = string(default=None)

        [protocol]
        # name of the most recently used protocol
        name = string(default=None)

        [plugins]
        # directory containing microdrop plugins
        directory = string(default=None)

        # list of enabled plugins
        enabled = string_list(default=list())
        """

    def __init__(self, filename=None):
        self.load(filename)

    def __getitem__(self, i):
        return self.data[i]

    def load(self, filename=None):
        """
        Load a Config object from a file.

        Args:
            filename: path to file. If None, try loading from the default
                location, and if there's no file, create a Config object
                with the default options.
        Raises:
            IOError: The file does not exist.
            ConfigObjError: There was a problem parsing the config file.
            ValidationError: There was a problem validating one or more fields.
        """
        if filename is None:
            logger.info("Using default configuration.")
            self.filename = self.default_config_path
        elif not path(filename).exists():
            raise IOError
        else:
            self.filename = filename
            logger.info("Loading config file from %s" % self.filename)
        self.data = ConfigObj(self.filename, configspec=self.spec.split("\n"))
        self._validate()

    def save(self, filename=None):
        if filename == None:
            filename = self.filename
        # make sure that the parent directory exists
        path(filename).parent.makedirs_p()
        with open(filename, 'w') as f:
            self.data.write(outfile=f)

    def _validate(self):
        # set all str values that are 'None' to None
        def set_str_to_none(d):
            for k, v in d.items():
                if type(v)==Section:
                    set_str_to_none(v)
                else:
                    if type(v)==str and v=='None':
                        d[k]=None
        set_str_to_none(self.data)
        validator = Validator()
        results = self.data.validate(validator, copy=True)
        if results != True:
            logger.error('Config file validation failed!')
            for (section_list, key, _) in flatten_errors(self.data, results):
                if key is not None:
                    logger.error('The "%s" key in the section "%s" failed '
                                 'validation' % (key, ', '.join(section_list)))
                else:
                    logger.error('The following section was missing:%s ' %
                                 ', '.join(section_list))
            raise ValidationError
        self.data.filename = self.filename
        self._init_data_dir()
        self._init_plugins_dir()

    def _init_data_dir(self):
        # If no user data directory is set in the configuration file, select
        # default directory based on the operating system.
        if os.name == 'nt':
            default_data_dir = home_dir().joinpath('Microdrop')
        else:
            default_data_dir = home_dir().joinpath('.microdrop')
        if 'data_dir' not in self.data:
            self.data['data_dir'] = default_data_dir
            warnings.warn('Using default Microdrop user data path: %s' %
                          default_data_dir)
        if not path(self['data_dir']).isdir():
            warnings.warn('Microdrop user data directory does not exist.')
            path(self['data_dir']).makedirs_p()
            warnings.warn('Created Microdrop user data directory: %s' %
                          self['data_dir'])

    def _init_plugins_dir(self):
        if self.data['plugins']['directory'] is None:
            self.data['plugins']['directory'] = (path(self['data_dir'])
                                                 .joinpath('plugins'))
        plugins_directory = path(self.data['plugins']['directory'])
        if not plugins_directory.isdir():
            plugins_directory.makedirs_p()
        if not plugins_directory.joinpath('__init__.py').isfile():
            plugins_directory.joinpath('__init__.py').touch()
