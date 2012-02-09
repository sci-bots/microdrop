"""
Copyright 2011 Ryan Fobel and Christian Fobel

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

from copy import deepcopy
import re
import logging
try:
    import cPickle as pickle
except ImportError:
    import pickle

import numpy as np

from logger import logger
from utility import Version, FutureVersionError


class Protocol():
    class_version = str(Version(0, 1))
    
    def __init__(self, n_channels=0, name=None):
        self.n_channels = n_channels
        self.steps = [Step()]
        self.name = None
        self.plugin_data = {}
        self.plugin_fields = {}
        self.n_repeats=1
        self.current_step_number = 0
        self.current_repetition = 0
        self.version = self.class_version

    @classmethod
    def load(cls, filename):
        """
        Load a Protocol from a file.

        Args:
            filename: path to file.
        Raises:
            TypeError: file is not a Protocol.
            FutureVersionError: file was written by a future version of the
                software.
        """
        logger.debug("[Protocol].load(\"%s\")" % filename)
        logger.info("Loading Protocol from %s" % filename)
        f = open(filename, 'rb')
        out = pickle.load(f)
        f.close()
        # check type
        if out.__class__!=cls:
            raise TypeError
        if not hasattr(out, 'version'):
            out.version = str(Version(0))
        elif not isinstance(out.version, str):
            out.version = str(out.version)
        out._upgrade()
        return out

    def _upgrade(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logger.debug("[Protocol]._upgrade()")
        version = Version.fromstring(self.version)
        logger.debug('[Protocol] version=%s, class_version=%s' % (str(version), self.class_version))
        version_010 = Version(major=0, minor=1)
        class_version = Version.fromstring(self.class_version)
        if version > class_version:
            logger.debug('[Protocol] version>class_version')
            raise FutureVersionError(Version.fromstring(self.class_version), version)
        elif version < version_010:
            # We need to convert plugin_data to pickled strings
            for k, v in self.plugin_data.iteritems():
                if v:
                    self.plugin_data[k] = pickle.dumps(v)
            for step in self.steps:
                for k, v in step.plugin_data.iteritems():
                    step.plugin_data[k] = pickle.dumps(v)
            self.version = str(version_010)
            logger.warning('[Protocol] upgraded protocol from version %s to %s'\
                    % (str(version), str(class_version)))
        elif version < class_version:
            pass
        # else the versions are equal and don't need to be upgraded

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

    def get_data(self, plugin_name):
        logging.debug('[Protocol] plugin_data=%s' % self.plugin_data)
        value = self.plugin_data.get(plugin_name)
        if value:
            return pickle.loads(value)
        return None

    def set_data(self, plugin_name, data):
        self.plugin_data[plugin_name] = pickle.dumps(data)

    def __len__(self):
        return len(self.steps)

    def __getitem__(self, i):
        return self.steps[i]

    def save(self, filename):
        f = open(filename, 'wb')
        #import pudb; pudb.set_trace()
        pickle.dump(self, f, -1)
        f.close()

    def set_number_of_channels(self, n_channels):
        self.n_channels = n_channels

    def current_step(self):
        return self.steps[self.current_step_number]

    def insert_step(self):
        self.steps.insert(self.current_step_number,
                          Step())

    def copy_step(self):
        self.steps.insert(self.current_step_number,
            Step(plugin_data=deepcopy(self.current_step().plugin_data)))
        self.next_step()

    def delete_step(self):
        if len(self.steps) > 1:
            del self.steps[self.current_step_number]
            if self.current_step_number == len(self.steps):
                self.current_step_number -= 1
        else: # reset first step
            self.steps = [Step()]

    def next_step(self):
        if self.current_step_number == len(self.steps) - 1:
            self.steps.append(Step())
        self.goto_step(self.current_step_number + 1)
        
    def next_repetition(self):
        if self.current_repetition < self.n_repeats - 1:
            self.current_repetition += 1
            self.goto_step(0)
            
    def prev_step(self):
        if self.current_step_number > 0:
            self.goto_step(self.current_step_number - 1)

    def first_step(self):
        self.current_repetition = 0
        self.goto_step(0)

    def last_step(self):
        self.goto_step(len(self.steps) - 1)

    def goto_step(self, step):
        self.current_step_number = step
        

class Step(object):
    def __init__(self, plugin_data=None):
        if plugin_data is None:
            self.plugin_data = {}
        else:
            self.plugin_data = deepcopy(plugin_data)

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

    def get_data(self, plugin_name):
        logging.debug('[Step] plugin_data=%s' % self.plugin_data)
        value = self.plugin_data.get(plugin_name)
        if value:
            return pickle.loads(value)
        return None

    def set_data(self, plugin_name, data):
        self.plugin_data[plugin_name] = pickle.dumps(data)
