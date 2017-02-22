"""
Copyright 2011 Ryan Fobel

This file is part of dmf_control_board.

MicroDrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

MicroDrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with MicroDrop.  If not, see <http://www.gnu.org/licenses/>.
"""
from StringIO import StringIO
from collections import namedtuple
from contextlib import closing
import logging
import os
import platform
import re
import subprocess
import sys
import traceback

from path_helpers import path
from pyutilib.component.core import ExtensionPoint, PluginGlobals
# TODO Update plugins to import from `pyutilib.component.core` directly
# instead of importing from here.
from pyutilib.component.core import Plugin, SingletonPlugin, implements
from run_exe import run_exe
import task_scheduler

from .interfaces import IPlugin, IWaveformGenerator, ILoggingPlugin


ScheduleRequest = namedtuple('ScheduleRequest', 'before after')


def load_plugins(plugins_dir='plugins'):
    '''
    Import each Python plugin module in the specified directory and create an
    instance of each contained plugin class for which an instance has not yet
    been created.

    Parameters
    ----------
    plugins_dir : str
        Directory containing zero or more Python plugin modules to import.
    import_from_parent : bool
        Add parent of specified directory to system path and import
        ``<parent>.<module>``.

        ..notes::
            **Not recommended**, but kept as default to maintain legacy
            protocol compatibility.

    Returns
    -------
    list
        Newly created plugins (plugins are not recreated if they were
        previously loaded.)
    '''
    logging.info('Loading plugins:')
    if plugins_dir.parent.abspath() not in sys.path:
        sys.path.insert(0, plugins_dir.parent.abspath())

    for package in plugins_dir.dirs():
        try:
            logging.info('\t %s' % package.abspath())
            import_statement = 'import %s.%s' % \
                (plugins_dir.name, package.name)
            logging.debug(import_statement)
            exec(import_statement)
        except Exception:
            logging.info(''.join(traceback.format_exc()))
            logging.error('Error loading %s plugin.', package.name,
                          exc_info=True)

    # Create an instance of each of the plugins, but set it to disabled
    e = PluginGlobals.env('microdrop.managed')
    for class_ in e.plugin_registry.values():
        service = class_()
        service.disable()


def log_summary():
    '''
    Dump summary of plugins to log.
    '''
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


def get_plugin_names(env=None):
    '''
    Parameters
    ----------
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    list(str)
        List of plugin names (e.g., ``['StepLabelPlugin', ...]``).
    '''
    if env is None:
        env = 'pca'
    e = PluginGlobals.env(env)
    return list(e.plugin_registry.keys())


def get_service_class(name, env='microdrop.managed'):
    '''
    Parameters
    ----------
    name : str
        Plugin class name (e.g., ``App``).
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    class
        Class type matching specified plugin class name.

        ..notes::
            Returns actual class type -- **not** an instance of the plugin
            service.
    '''
    e = PluginGlobals.env(env)
    if name not in e.plugin_registry:
        raise KeyError, 'No plugin registered with name: %s' % name
    return e.plugin_registry[name]


def get_service_instance_by_name(name, env='microdrop.managed'):
    '''
    Parameters
    ----------
    name : str
        Plugin name (e.g., ``wheelerlab.zmq_hub_plugin``).

        Corresponds to ``plugin_name`` key in plugin ``properties.yml`` file.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    object
        Active service instance matching specified plugin name.
    '''
    e = PluginGlobals.env(env)
    plugins = [p for i, p in enumerate(e.services) if name == p.name]
    if plugins:
        return plugins[0]
    else:
        raise KeyError, 'No plugin registered with name: %s' % name


def get_service_instance_by_package_name(name, env='microdrop.managed'):
    '''
    Parameters
    ----------
    name : str
        Plugin Python module name (e.g., ``dmf_control_board_plugin``).

        Corresponds to ``package_name`` key in plugin ``properties.yml`` file.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    object
        Active service instance matching specified plugin module name.
    '''
    e = PluginGlobals.env(env)
    plugins = [p for i, p in enumerate(e.services) \
               if name == get_plugin_package_name(p.__class__.__module__)]
    if plugins:
        return plugins[0]
    else:
        raise KeyError, 'No plugin registered with package name: %s' % name


def get_plugin_package_name(class_name):
    '''
    Parameters
    ----------
    class_name : str
        Fully-qualified class name (e.g.,
        ``'plugins.dmf_control_board_plugin'``).

    Returns
    -------
    str
        Relative module name (e.g., ``'dmf_control_board_plugin'``)
    '''
    match = re.search(r'plugins\.(?P<name>.*)',
                      class_name)
    if match is None:
        logging.error('Could not determine package name from: %s'\
                % class_name)
        return None
    return match.group('name')


def get_service_instance(class_, env='microdrop.managed'):
    '''
    Parameters
    ----------
    class_ : class
        Plugin class type.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    object or None
        Registered service instance for the specified plugin class type.

        Returns ``None`` if no service is registered for the specified plugin
        class type.
    '''
    e = PluginGlobals.env(env)
    for service in e.services:
        if isinstance(service, class_):
            # A plugin of this type is registered
            return service
    return None


def get_service_names(env='microdrop.managed'):
    '''
    Parameters
    ----------
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    list
        List of plugin names (e.g., ``['wheelerlab.step_label_plugin', ...]``).
    '''
    e = PluginGlobals.env(env)
    service_names = []
    for name in get_plugin_names(env):
        plugin_class = e.plugin_registry[name]
        service = get_service_instance(plugin_class, env=env)
        service_names.append(service.name)
    return service_names


def get_schedule(observers, function):
    '''
    Generate observer order based on scheduling requests for specified
    function.

    Parameters
    ----------
    observers : dict
        Mapping from service names to service instances.
    function : str
        Name of function to generate schedule for.

    Returns
    -------
    list
        List of observer service names in scheduled order.
    '''
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
        return scheduler.get_schedule()
    else:
        return observers.keys()


def get_observers(function, interface=IPlugin):
    '''
    Get dictionary of observers implementing the specified function.

    Parameters
    ----------
    function : str
        Name of function to generate schedule for.
    interface : class, optional
        Plugin interface class.

    Returns
    -------
    dict
        Mapping from service names to service instances.
    '''
    observers = {}
    for obs in ExtensionPoint(interface):
        if hasattr(obs, function):
            observers[obs.name] = obs
    return observers


def emit_signal(function, args=None, interface=IPlugin):
    '''
    Call specified function on each enabled plugin implementing the function
    and collect results.

    Parameters
    ----------
    function : str
        Name of function to generate schedule for.
    interface : class, optional
        Plugin interface class.

    Returns
    -------
    dict
        Mapping from each service name to the respective function return value.
    '''
    try:
        observers = get_observers(function, interface)
        schedule = get_schedule(observers, function)
        return_codes = {}
        for observer_name in schedule:
            observer = observers[observer_name]
            logging.debug('emit_signal: %s.%s()' % (observer.name, function))
            try:
                if args is None:
                    args = []
                elif type(args) is not list:
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
                logging.info(''.join(traceback.format_exc()))
        return return_codes
    except Exception, why:
        logging.error(why, exc_info=True)
        return {}


def enable(name, env='microdrop.managed'):
    '''
    Enable specified plugin.

    Parameters
    ----------
    name : str
        Plugin name (e.g., ``wheelerlab.zmq_hub_plugin``).

        Corresponds to ``plugin_name`` key in plugin ``properties.yml`` file.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').
    '''
    service = get_service_instance_by_name(name, env)
    if not service.enabled():
        service.enable()
        logging.info('[PluginManager] Enabled plugin: %s' % name)
    if hasattr(service, "on_plugin_enable"):
        service.on_plugin_enable()
    emit_signal('on_plugin_enabled', [env, service])


def disable(name, env='microdrop.managed'):
    '''
    Disable specified plugin.

    Parameters
    ----------
    name : str
        Plugin name (e.g., ``wheelerlab.zmq_hub_plugin``).

        Corresponds to ``plugin_name`` key in plugin ``properties.yml`` file.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').
    '''
    service = get_service_instance_by_name(name, env)
    if service and service.enabled():
        service.disable()
        if hasattr(service, "on_plugin_disable"):
            service.on_plugin_disable()
        emit_signal('on_plugin_disabled', [env, service])
        logging.info('[PluginManager] Disabled plugin: %s' % name)


PluginGlobals.pop_env()
