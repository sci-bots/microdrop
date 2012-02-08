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

try:
    import cPickle as pickle
except ImportError:
    import pickle

import numpy as np

from logger import logger
from utility import Version


class DmfDevice():
    class_version = str(Version(0,1,0))
    def __init__(self):
        self.electrodes = {}
        self.x_min = np.Inf
        self.x_max = 0
        self.y_min = np.Inf
        self.y_max = 0
        self.name = None
        self.scale = None
        self.version = self.__class__.class_version

    @classmethod
    def load(cls, filename):
        logger.debug("[DmfDevice].load")
        f = open(filename, 'rb')
        out = pickle.load(f)
        f.close()
        # check type
        if out.__class__!=cls:
            raise TypeError
        if not hasattr(out, 'version'):
            out.version = '0'
        logger.info('[DmfDevice] version %s' % str(out.version))
        if Version.fromstring(out.version) != \
            Version.fromstring(out.class_version):
            out.upgrade()
        return out

    def upgrade(self):
        logger.debug("[DmfDevice].upgrade")
        version = Version.fromstring(self.version)
        if version < Version(0,1):
            self.version = '0.1'
            self.scale = None
            logger.info('[DmfDevice] upgrade to version 0.1')

    def save(self, filename):
        f = open(filename, 'wb')
        pickle.dump(self, f, -1)
        f.close()

    def geometry(self):
        return (self.x_min, self.y_min,
                self.x_max-self.x_min,
                self.y_max-self.y_min) 

    def add_electrode_path(self, path):
        e = Electrode(path)
        self.electrodes[e.id] = e
        for electrode in self.electrodes.values():
            if electrode.x_min < self.x_min:
                self.x_min = electrode.x_min 
            if electrode.x_max > self.x_max:
                self.x_max = electrode.x_max 
            if electrode.y_min < self.y_min:
                self.y_min = electrode.y_min
            if electrode.y_max > self.y_max:
                self.y_max = electrode.y_max
        return e.id

    def add_electrode_rect(self, x, y, width, height=None):
        if height is None:
            height = width
        path = []
        path.append({'command':'M','x':x,'y':y})
        path.append({'command':'L','x':x+width,'y':y})
        path.append({'command':'L','x':x+width,'y':y+height})
        path.append({'command':'L','x':x,'y':y+height})
        path.append({'command':'Z'})
        return self.add_electrode_path(path)
    
    def connect(self, id, channel):
        if self.electrodes[id].channels.count(channel):
            pass
        else:
            self.electrodes[id].channels.append(channel)
            
    def disconnect(self, id, channel):
        if self.electrodes[id].channels.count(channel):
            self.electrodes[id].channels.remove(channel)
            
    def max_channel(self):
        max_channel = 0
        for electrode in self.electrodes.values():
            if electrode.channels and max(electrode.channels) > max_channel:
                max_channel = max(electrode.channels)
        return max_channel
        
class Electrode:
    next_id = 0
    def __init__(self, path):
        self.id = Electrode.next_id
        Electrode.next_id += 1
        self.path = path
        self.state = 0
        self.channels = []
        self.x_min = np.Inf
        self.y_min = np.Inf
        self.x_max = 0
        self.y_max = 0
        for step in path:
            if step.has_key('x') and step.has_key('y'):
                if float(step['x']) < self.x_min:
                    self.x_min = float(step['x'])
                if float(step['x']) > self.x_max:
                    self.x_max = float(step['x'])
                if float(step['y']) < self.y_min:
                    self.y_min = float(step['y'])
                if float(step['y']) > self.y_max:
                    self.y_max = float(step['y'])

    def area(self):
        return (self.x_max-self.x_min)*(self.y_max-self.y_min)

    def contains(self, x, y):
        if self.x_min < x < self.x_max and self.y_min < y < self.y_max:
            return True
        else:
            return False
