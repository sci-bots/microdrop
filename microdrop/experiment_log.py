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
import pickle
import time

import numpy as np
from path import path
import yaml

from utility import is_int, Version, VersionError, FutureVersionError
from logger import logger


class ExperimentLog():
    class_version = str(Version(0))

    @classmethod
    def load(cls, filename):
        """
        Load an experiment log from a file.

        Args:
            filename: path to file.
        Raises:
            TypeError: file is not an experiment log.
            FutureVersionError: file was written by a future version of the
                software.
        """
        logger.debug("[ExperimentLog].load(\"%s\")" % filename)
        logger.info("Loading Experiment log from %s" % filename)
        out = None
        with open(filename, 'rb') as f:
            try:
                out = pickle.load(f)
                logger.debug("Loaded object from pickle.")
            except Exception, e:
                logger.debug("Not a valid pickle file. %s." % e)
        if out==None:
            with open(filename, 'rb') as f:
                try:
                    out = yaml.load(f)
                    logger.debug("Loaded object from YAML file.")
                except Exception, e:
                    logger.debug("Not a valid YAML file. %s." % e)
        if out==None:
            raise TypeError
        out.filename = filename
        # check type
        if out.__class__!=cls:
            raise TypeError
        if not hasattr(out, 'version'):
            out.version = str(Version(0))
        out._upgrade()
        return out
    
    def __init__(self, directory=None):
        self.directory = directory
        self.data = []
        self.version = self.class_version
        self._get_next_id()

    def _upgrade(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logger.debug("[ExperimentLog]._upgrade()")
        version = Version.fromstring(self.version)
        logger.debug('[ExperimentLog] version=%s, class_version=%s' % (str(version), self.class_version))
        if version > Version.fromstring(self.class_version):
            logger.debug('[ExperimentLog] version>class_version')
            raise FutureVersionError
        elif version < Version.fromstring(self.class_version): 
            pass
        # else the versions are equal and don't need to be upgraded
        
    def save(self, filename=None, format='yaml'):
        if filename==None:
            log_path = self.get_log_path()
            filename = os.path.join(log_path,"data")
        else:
            log_path = path(filename).parent 
        if self.data:
            with open(filename, 'wb') as f:
                if format=='pickle':
                    pickle.dump(self, f, -1)
                elif format=='yaml':
                    yaml.dump(self, f)
                else:
                    raise TypeError
        return log_path

    def start_time(self):
        data = self.get("start time")
        for val in data:
            if val:
                return val
        start_time = time.time()
        self.data.append({"start time":start_time})
        return start_time

    def get_log_path(self):
        log_path = os.path.join(self.directory, str(self.experiment_id))
        if(os.path.isdir(log_path)==False):
            os.mkdir(log_path)
        return log_path

    def add_step(self, step_number):
        self.data.append({"step": step_number, 
                         "time": time.time() - self.start_time()})

    def add_data(self, data):
        for k, v in data.items():
            self.data[-1][k]=v

    def get(self, name):
        var = []
        for d in self.data:
            if d.keys().count(name):
                var.append(d[name])
            else:
                var.append(None)
        return var

    def _get_next_id(self):
        if self.directory is None:
            self.experiment_id = None
            return
        if(os.path.isdir(self.directory)==False):
            os.mkdir(self.directory)
        logs = os.listdir(self.directory)
        self.experiment_id = 0
        for i in logs:
            if is_int(i):
                if int(i) >= self.experiment_id:
                    self.experiment_id = int(i) + 1
