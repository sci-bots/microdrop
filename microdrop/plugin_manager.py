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
import sys
from StringIO import StringIO
from contextlib import closing

from pyutilib.component.core import Interface, ExtensionPoint, implements, PluginGlobals
import pyutilib.component.loader
from path import path
import logging

import utility

if utility.PROGRAM_LAUNCHED:
    from pyutilib.component.core import SingletonPlugin, Plugin, PluginGlobals
else:
    from pyutilib.component.config import ManagedPlugin as SingletonPlugin

PluginGlobals.push_env('microdrop.managed')
PluginGlobals.pop_env()


PluginGlobals.push_env('microdrop')

class PluginManager():
    def load_plugins(self, plugins_dir='plugins'):
        plugins_dir = path(plugins_dir)
        logging.info('Loading plugins:')
        if plugins_dir.parent.abspath() not in sys.path:
            sys.path.insert(0, plugins_dir.parent.abspath())
        for d in plugins_dir.dirs():
            package = (d / path('microdrop'))
            if package.isdir(): 
                logging.info('\t %s' % package.abspath())
                import_statement = 'import %s.%s.microdrop' % (plugins_dir.name, d.name)
                logging.info(import_statement)
                exec(import_statement)

    def log_summary(self):
        observers = ExtensionPoint(IPlugin)
        logging.info('Registered plugins:')
        for observer in observers:
            logging.info('\t %s' % observer)
        observers = ExtensionPoint(IWaveformGenerator)
        logging.info('Registered function generator plugins:')
        for observer in observers:
            logging.info('\t %s' % observer)
        observers = ExtensionPoint(ILoggingPlugin)
        logging.info('Registered logging plugins:')
        for observer in observers:
            logging.info('\t %s' % observer)

    def get_plugin_names(self, env=None):
        if env is None:
            env = 'pca'
        e = PluginGlobals.env(env)
        return list(e.plugin_registry.keys())

    def disable(self, name, env='microdrop.managed'):
        e = PluginGlobals.env(env)
        if name not in e.plugin_registry:
            raise KeyError, 'No plugin registered with name: %s' % name
        class_ = e.plugin_registry[name]
        service = self.get_service_instance(class_, env)
        if service and service.enabled():
            if hasattr(service, "on_plugin_disable"):
                service.on_plugin_disable()
            service.disable()
            logging.info('[PluginManager] Disabled plugin: %s' % name)

    def enable(self, name, env='microdrop.managed'):
        e = PluginGlobals.env(env)
        if name not in e.plugin_registry:
            raise KeyError, 'No plugin registered with name: %s' % name
        PluginClass = e.plugin_registry[name]
        service = self.get_service_instance(PluginClass, env)
        if service is None:
            # There is not currently any plugin registered of the specified
            # type.
            try:
                service = PluginClass()
            except Exception, why:
                service_instance = self.get_service_instance(PluginClass)
                with closing(StringIO()) as message:
                    if service_instance:
                            if hasattr(service_instance, "name"):
                                print >> message, '%s plugin crashed during initialization:' % str(PluginClass),
                            # Deactivate in plugin registry since the plugin was not
                            # initialized properly.
                            service_instance.deactivate()
                    print >> message, str(why)
                    logging.error(message.getvalue().strip())
                return None
        if not service.enabled():
            service.enable()
            logging.info('[PluginManager] Enabled plugin: %s' % name)
        if hasattr(service, "on_plugin_enable"):
            service.on_plugin_enable()
        return service

    def get_service_instance(self, class_, env='microdrop.managed'):
        e = PluginGlobals.env(env)
        for service in e.services:
            if isinstance(service, class_):
                # A plugin of this type is registered
                return service
        return None
        

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


    class IVideoPlugin(object):    
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
        def on_plugin_disable():
            """
            Handler called once the plugin instance has been disabled.
            """
            pass
        
        def on_plugin_enable():
            """
            Handler called once the plugin instance has been enabled.
            """
            pass
        
        def on_app_init():
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

        def on_protocol_update(self):
            """
            Handler called whenever views of the protocol need to update.

            Returns:
                True if the protocol should be updated again (e.g., if a feedback
                plugin wants to signal that the step should be repeated)
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

        def on_dmf_device_update(self):
            """
            Handler called whenever views of the DMF device need to update.
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
        
        def on_step_options_changed(self, plugin, step_number):
            """
            Handler called when the step options are changed for a particular
            plugin.  This will, for example, allow for GUI elements to be
            updated based on step specified.

            Parameters:
                plugin : plugin instance for which the step options changed
                step_number : step number that the options changed for
            """
            pass


    class IVideoPlugin(Interface):
        def on_new_frame(self, frame):
            pass


def emit_signal(function, args=[], interface=IPlugin, by_observer=False):
    observers = ExtensionPoint(interface)
    if by_observer:
        return_codes = {}
    else:
        return_codes = []
    for observer in observers:
        if hasattr(observer, function):
            try:
                if type(args) is not list:
                    args = [args]
                f = getattr(observer, function)
                if by_observer:
                    return_codes[observer.name] = f(*args)
                else:
                    return_code = f(*args)
                    return_codes.append(return_code)
            except Exception, why:
                with closing(StringIO()) as message:
                    if hasattr(observer, "name"):
                        if interface == ILoggingPlugin:
                            # If this is a logging plugin, do not try to log since
                            # that will result in infinite recursion.  Instead,
                            # just continute onto the next plugin.
                            continue
                        print >> message, '%s plugin crashed processing %s signal.' % (observer.name, function)
                    print >> message, 'Reason:', str(why)
                    logging.error(message.getvalue().strip())
                logging.debug(''.join(traceback.format_stack()))
    return return_codes

PluginGlobals.pop_env()
