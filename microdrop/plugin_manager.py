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
from collections import namedtuple

from pyutilib.component.core import Interface, ExtensionPoint, implements, \
    PluginGlobals
import pyutilib.component.loader
from path import path
import logging

import utility
import task_scheduler

if utility.PROGRAM_LAUNCHED:
    from pyutilib.component.core import SingletonPlugin, Plugin, PluginGlobals
else:
    from pyutilib.component.core import Plugin
    from pyutilib.component.config import ManagedPlugin as SingletonPlugin

PluginGlobals.push_env('microdrop.managed')
PluginGlobals.pop_env()


PluginGlobals.push_env('microdrop')


ScheduleRequest = namedtuple('ScheduleRequest', 'before after')


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
        def get_schedule_requests(self, function_name):
            """
            Returns a list of scheduling requests (i.e., ScheduleRequest
            instances) for the function specified by function_name.
            """
            return []

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
            Handler called when the DMF device changes (e.g., when a new device
            is loaded).
            """
            pass
        
        def on_experiment_log_changed(self):
            """
            Handler called when the experiment log changes (e.g., when a
            protocol finishes running.
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

        def on_step_run(self):
            """
            Handler called whenever a step is executed.

            Returns:
                True if the step should be run again (e.g., if a feedback
                plugin wants to signal that the step should be repeated)
            """
            pass

        def get_step_form_class(self):
            pass

        def get_step_values(self, step_number=None):
            pass

    class IVideoPlugin(Interface):
        def on_new_frame(self, frame):
            pass


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
                import_statement = 'import %s.%s.microdrop' % \
                    (plugins_dir.name, d.name)
                logging.debug(import_statement)
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
                                print >> message, \
                                '%s plugin crashed during initialization:' % \
                                str(PluginClass),
                            # Deactivate in plugin registry since the plugin
                            # was not initialized properly.
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

    @staticmethod
    def get_schedule(plugin_names):
        core_scheduler = task_scheduler.TaskScheduler(plugin_names)
        core_scheduler.request_order('microdrop.app', 'microdrop.gui.main_window_controller')
        core_scheduler.request_order('microdrop.gui.main_window_controller', 'microdrop.gui.protocol_grid_controller')
        core_scheduler.request_order('microdrop.gui.main_window_controller', 'wheelerlab.dmf_control_board_1.2')
        core_scheduler.request_order('microdrop.gui.main_window_controller', 'microdrop.gui.protocol_controller')
        core_scheduler.request_order('microdrop.gui.main_window_controller', 'microdrop.gui.dmf_device_controller')
        core_scheduler.request_order('microdrop.gui.dmf_device_controller', 'wheelerlab.dmf_control_board_1.2')
        return core_scheduler.get_schedule()

    def emit_signal(self, function, args=[], interface=IPlugin):
        observers = dict([(obs.name, obs) for obs in ExtensionPoint(interface)])

        # Query plugins for schedule requests for 'function'
        schedule_requests = {}
        for observer in observers.values():
            if hasattr(observer, 'get_schedule_requests'):
                schedule_requests[observer.name] =\
                        observer.get_schedule_requests(function)

        if schedule_requests:
            scheduler = task_scheduler.TaskScheduler(observers.keys())
            for request in [r for name, requests in schedule_requests.items() for r in requests]:
                try:
                    scheduler.request_order(*request)
                except AssertionError:
                    logging.info('[PluginManager] emit_signal(%s) could not '\
                            'add schedule request %s' % (function, request))
                    continue
            schedule = scheduler.get_schedule()
        else:
            schedule = observers.keys()

        return_codes = {}
        for observer_name in schedule:
            observer = observers[observer_name]
            if hasattr(observer, function):
                logging.debug('emit_signal: %s.%s()' % (observer.name, function))                    
                try:
                    if type(args) is not list:
                        args = [args]
                    f = getattr(observer, function)
                    return_codes[observer.name] = f(*args)
                except Exception, why:
                    with closing(StringIO()) as message:
                        if hasattr(observer, "name"):
                            if interface == ILoggingPlugin:
                                # If this is a logging plugin, do not try to log
                                # since that will result in infinite recursion. 
                                # Instead, just continue onto the next plugin.
                                continue
                            print >> message, \
                                '%s plugin crashed processing %s signal.' % \
                                (observer.name, function)
                        print >> message, 'Reason:', str(why)
                        logging.error(message.getvalue().strip())
                    logging.debug(''.join(traceback.format_stack()))
        return return_codes


PluginGlobals.pop_env()
