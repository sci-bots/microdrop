"""
Copyright 2011 Ryan Fobel

This file is part of dmf_control_board.

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

import traceback

from pyutilib.component.core import Interface, ExtensionPoint, implements
import pyutilib.component.loader
from path import path
import logging

import utility

if utility.PROGRAM_LAUNCHED:
    from pyutilib.component.core import SingletonPlugin
else:
    from pyutilib.component.config import ManagedPlugin as SingletonPlugin


class PluginManager():
    def __init__(self):
        logging.info('Loading plugins:')
        for d in path("plugins").dirs():
            package = (d / path("microdrop"))
            if package.isdir(): 
                logging.info('\t %s' % package.abspath())
                exec("import plugins.%s.microdrop" % d.name) 
        observers = ExtensionPoint(IPlugin)
        logging.info('Registered plugins:')
        for observer in observers:
            logging.info('\t %s' % observer)
        observers = ExtensionPoint(IWaveformGenerator)
        logging.info('Registered function generator plugins:')
        for observer in observers:
            logging.info('\t %s' % observer)
        observers = ExtensionPoint(IWaveformGenerator)
        logging.info('Registered logging plugins:')
        for observer in observers:
            logging.info('\t %s' % observer)


# Workaround to allow Sphinx autodoc to run.  If the program is not actually
# running, we are just being imported here, so declare plugin interfaces as
# plain-old objects, rather than Interface sub-classes.
if not utility.PROGRAM_LAUNCHED:
    class IPlugin(object):    
        __interface_namespace__ = None

    class IWaveformGenerator(object):
        __interface_namespace__ = None

    class ILoggingPlugin(object):
        __interface_namespace__ = None
else:
    class ILoggingPlugin(Interface):
        def on_debug(self, record):
            pass

        def on_info(self, record):
            pass

        def on_warning(self, record):
            pass

        def on_error(self, record):
            pass

        def on_critical(self, record):
            pass


    class IWaveformGenerator(Interface):
        def set_voltage(self, voltage):
            """
            Set the waveform voltage.
            
            Parameters:
                voltage : RMS voltage
            """
            pass
        
        def set_frequency(self, frequency):
            """
            Set the waveform frequency.
            
            Parameters:
                frequency : frequency in Hz
            """
            pass


    class IPlugin(Interface):    
        def on_app_init(app=None):
            """
            Handler called once when the Microdrop application starts.
            
            Plugins should store a reference to the app object if they need to
            access other components.
            """
            pass
        
        def on_app_exit(self):
            """
            Handler called just before the Microdrop application exists. 
            """
            pass

        def on_protocol_update(self, data):
            """
            Handler called whenever views of the protocol need to update.

            Parameters:
                data : dictionary to store experiment log data for the current step

            Returns:
                True if the protocol should be updated again (e.g., if a feedback
                plugin wants to signal that the step should be repeated)
            """
            pass

        def on_delete_protocol_step(self):
            """
            Handler called whenever a protocol step is deleted.
            """
            pass

        def on_insert_protocol_step(self):
            """
            Handler called whenever a protocol step is inserted.
            """
            pass

        def on_protocol_save(self):
            """
            Handler called when a protocol is saved.
            """
            pass
        
        def on_protocol_load(self, version, data):
            """
            Handler called when a protocol is loaded.
            """
            pass

        def on_protocol_run(self):
            """
            Handler called when a protocol starts running.
            """
            pass
        
        def on_protocol_pause(self):
            """
            Handler called when a protocol is paused.
            """
            pass

        def on_dmf_device_changed(self):
            """
            Handler called when the DMF device changes (e.g., when a new device is
            loaded).
            """
            pass

        def on_experiment_log_changed(self):
            """
            Handler called when the experiment log changes (e.g., when a protocol
            finishes running.
            """
            pass
        
        def on_experiment_log_selection_changed(self, data):
            """
            Handler called whenever the experiment log selection changes.

            Parameters:
                data : experiment log data (list of dictionaries, one per step)
                    for the selected steps
            """
            pass


def emit_signal(function, args=[], interface=IPlugin):
    return_codes = []
    observers = ExtensionPoint(interface)
    for observer in observers:
        if hasattr(observer, function):
            try:
                if type(args) is not list:
                    args = [args]
                f = getattr(observer, function)
                return_code = f(*args)
                return_codes.append(return_code)
            except Exception, why:
                if hasattr(observer, "name"):
                    logging.error('%s plugin crashed.' % observer.name)
                logging.error(str(why))
                logging.error(''.join(traceback.format_stack()))
    return return_codes
