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


def load(filename):
    f = open(filename, 'rb')
    protocol = pickle.load(f)
    f.close()
    return protocol

class Protocol():
    def __init__(self, n_channels=0, name=None):
        self.n_channels = n_channels
        self.steps = [Step()]
        self.name = None
        self.plugin_data = {}
        self.plugin_fields = {}

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
        return self.plugin_data.get(plugin_name)

    def set_data(self, plugin_name, data):
        self.plugin_data[plugin_name] = data

    def __len__(self):
        return len(self.steps)

    def __getitem__(self, i):
        return self.steps[i]

    def save(self, filename):
        f = open(filename, 'wb')
        pickle.dump(self, f, -1)
        f.close()

    def set_number_of_channels(self, n_channels):
        self.n_channels = n_channels

    def current_step(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        return self.steps[options.current_step_number]

    def insert_step(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        self.steps.insert(options.current_step_number,
                          Step())

    def copy_step(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        self.steps.insert(options.current_step_number,
            Step(plugin_data=deepcopy(self.current_step().plugin_data)))
        self.next_step()

    def delete_step(self):
        if len(self.steps) > 1:
            options = self.get_data('microdrop.gui.protocol_controller')
            del self.steps[options.current_step_number]
            if options.current_step_number == len(self.steps):
                options.current_step_number -= 1
        else: # reset first step
            self.steps = [Step()]

    def next_step(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        if options.current_step_number == len(self.steps) - 1:
            self.steps.append(Step())
        self.goto_step(options.current_step_number + 1)
        
    def next_repetition(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        if options.current_repetition < options.n_repeats - 1:
            options.current_repetition += 1
            self.goto_step(0)
            
    def prev_step(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        if options.current_step_number > 0:
            self.goto_step(options.current_step_number - 1)

    def first_step(self):
        options = self.get_data('microdrop.gui.protocol_controller')
        options.current_repetition = 0
        self.goto_step(0)

    def last_step(self):
        self.goto_step(len(self.steps) - 1)

    def goto_step(self, step):
        options = self.get_data('microdrop.gui.protocol_controller')
        options.current_step_number = step
        

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
        return self.plugin_data.get(plugin_name)

    def set_data(self, plugin_name, data):
        self.plugin_data[plugin_name] = data
