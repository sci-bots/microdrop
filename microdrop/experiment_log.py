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

import numpy as np

from utility import is_int, path


def load(filename):
    f = open(filename,"rb")
    log = pickle.load(f)
    f.close()
    return log

class ExperimentLog():
    def __init__(self, directory=None):
        self.directory = directory
        self.experiment_id = None
        self.data = []

    def get_next_id(self):
        if self.directory is None:
            raise Exception("No device directory set.")
        elif self.experiment_id is None:
            if(os.path.isdir(self.directory)==False):
                os.mkdir(self.directory)
            logs = os.listdir(self.directory)
            self.experiment_id = 0
            for i in logs:
                if is_int(i):
                    if int(i) >= self.experiment_id:
                        self.experiment_id = int(i) + 1
        return self.experiment_id 

    def get_log_path(self):
        self.experiment_id = None
        log_path = os.path.join(self.directory,str(self.get_next_id()))
        if(os.path.isdir(log_path)==False):
            os.mkdir(log_path)
        return log_path
        
    def add_data(self, data):
        self.data.append(data)
        
    def save(self, filename=None):
        if filename==None:
            log_path = self.get_log_path()
            filename = os.path.join(log_path,"data")
        else:
            log_path = path(filename).parent 
        if self.data:
            output = open(filename, 'wb')
            pickle.dump(self, output, -1)
            output.close()
        return log_path

    def get(self, name):
        var = []
        for i in self.data:
            if i.keys().count(name):
                var.append(i[name])
            else:
                var.append(None)
        return var

    def clear(self):
        # reset the log data
        self.experiment_id = None
        self.data = []