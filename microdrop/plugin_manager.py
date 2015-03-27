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
import logging
import re
import os
import platform
import subprocess

from path_helpers import path
import task_scheduler
import yaml
from run_exe import run_exe

from interfaces import (Plugin, IPlugin, PluginGlobals, ExtensionPoint,
                        IWaveformGenerator, ILoggingPlugin, IVideoPlugin,
                        SingletonPlugin, implements)


ScheduleRequest = namedtuple('ScheduleRequest', 'before after')


def load_plugins(plugins_dir='plugins'):
    plugins_dir = path(plugins_dir)
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
        except Exception, why:
            logging.info(''.join(traceback.format_exc()))
            logging.error('Error loading %s plugin.' % package.name)

    # Create an instance of each of the plugins, but set it to disabled
    e = PluginGlobals.env('microdrop.managed')
    for class_ in e.plugin_registry.values():
        service = class_()
        service.disable()


def post_install(install_path):
    # __NB__ The `cwd` directory ["is not considered when searching the
    # executable, so you can't specify the program's path relative to
    # `cwd`."][cwd].  Therefore, we manually change to the directory
    # containing the hook script and change back to the original working
    # directory when we're done.
    #
    # [cwd]: https://docs.python.org/2/library/subprocess.html#popen-constructor
    cwd = os.getcwd()
    if platform.system() in ('Linux', 'Darwin'):
        system_name = platform.system()
        hooks_path = install_path.joinpath('hooks', system_name).abspath()
        on_install_path = hooks_path.joinpath('on_plugin_install.sh')
        if on_install_path.isfile():
            # There is an `on_plugin_install` script to run.
            try:
                os.chdir(hooks_path)
                subprocess.check_call(['sh', on_install_path.name,
                                       sys.executable], cwd=hooks_path)
            finally:
                os.chdir(cwd)
    elif platform.system() == 'Windows':
        hooks_path = install_path.joinpath('hooks', 'Windows').abspath()
        for ext in ('exe', 'bat'):
            on_install_path = hooks_path.joinpath('on_plugin_install.%s' % ext)
            if on_install_path.isfile():
                # There is an `on_plugin_install` script to run.
                # Request elevated privileges if an error occurs.
                run_exe(on_install_path.name, '"%s"' % sys.executable,
                        try_admin=True, working_dir=hooks_path)
                break


def log_summary():
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
    observers = ExtensionPoint(IVideoPlugin)
    logging.info('Registered video plugins:')
    for observer in observers:
        logging.info('\t %s' % observer)


def get_plugin_names(env=None):
    if env is None:
        env = 'pca'
    e = PluginGlobals.env(env)
    return list(e.plugin_registry.keys())


def get_service_class(name, env='microdrop.managed'):
    e = PluginGlobals.env(env)
    if name not in e.plugin_registry:
        raise KeyError, 'No plugin registered with name: %s' % name
    return e.plugin_registry[name]


def get_service_instance_by_name(name, env='microdrop.managed'):
    e = PluginGlobals.env(env)
    plugins = [p for i, p in enumerate(e.services) if name == p.name]
    if plugins:
        return plugins[0]
    else:
        raise KeyError, 'No plugin registered with name: %s' % name


def get_service_instance_by_package_name(name, env='microdrop.managed'):
    e = PluginGlobals.env(env)
    plugins = [p for i, p in enumerate(e.services) \
               if name == get_plugin_package_name(p.__class__.__module__)]
    if plugins:
        return plugins[0]
    else:
        raise KeyError, 'No plugin registered with package name: %s' % name


def get_plugin_package_name(class_name):
    match = re.search(r'plugins\.(?P<name>.*)',
                      class_name)
    if match is None:
        logging.error('Could not determine package name from: %s'\
                % class_name)
        return None
    return match.group('name')


def get_service_instance(class_, env='microdrop.managed'):
    e = PluginGlobals.env(env)
    for service in e.services:
        if isinstance(service, class_):
            # A plugin of this type is registered
            return service
    return None


def get_service_names(env='microdrop.managed'):
    e = PluginGlobals.env(env)
    service_names = []
    for name in get_plugin_names(env):
        plugin_class = e.plugin_registry[name]
        service = get_service_instance(plugin_class, env=env)
        service_names.append(service.name)
    return service_names


def get_schedule(observers, function):
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
    observers = {}
    for obs in ExtensionPoint(interface):
        if hasattr(obs, function):
            observers[obs.name] = obs
    return observers


def emit_signal(function, args=[], interface=IPlugin):
    try:
        observers = get_observers(function, interface)
        schedule = get_schedule(observers, function)
        return_codes = {}
        for observer_name in schedule:
            observer = observers[observer_name]
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
                logging.info(''.join(traceback.format_exc()))
        return return_codes
    except Exception, why:
        logging.error(why)
        #import pudb; pudb.set_trace()
        return {}


def enable(name, env='microdrop.managed'):
    service = get_service_instance_by_name(name, env)
    if not service.enabled():
        service.enable()
        logging.info('[PluginManager] Enabled plugin: %s' % name)
    if hasattr(service, "on_plugin_enable"):
        service.on_plugin_enable()
    emit_signal('on_plugin_enabled', [env, service])


def disable(name, env='microdrop.managed'):
    service = get_service_instance_by_name(name, env)
    if service and service.enabled():
        service.disable()
        if hasattr(service, "on_plugin_disable"):
            service.on_plugin_disable()
        emit_signal('on_plugin_disabled', [env, service])
        logging.info('[PluginManager] Disabled plugin: %s' % name)


PluginGlobals.pop_env()
