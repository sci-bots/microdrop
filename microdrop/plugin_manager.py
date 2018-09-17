from StringIO import StringIO
from collections import namedtuple
from contextlib import closing
import logging
import pprint
import sys
import traceback

from pyutilib.component.core import ExtensionPoint, PluginGlobals
# TODO Update plugins to import from `pyutilib.component.core` directly
# instead of importing from here.
from pyutilib.component.core import Plugin, SingletonPlugin, implements
import path_helpers as ph
import task_scheduler

from .interfaces import IPlugin, IWaveformGenerator, ILoggingPlugin
from logging_helpers import _L, caller_name  #: .. versionadded:: 2.20


logger = logging.getLogger(__name__)


ScheduleRequest = namedtuple('ScheduleRequest', 'before after')


def load_plugins(plugins_dir='plugins', import_from_parent=True):
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


    .. versionchanged:: 2.25
        Do not import hidden directories (i.e., name starts with ``.``).

    .. versionchanged:: 2.30
        Import from `pyutilib` submodule in plugin instead, if it exists.
    '''
    logger = _L()  # use logger with function context
    logger.info('plugins_dir=`%s`', plugins_dir)
    plugins_dir = ph.path(plugins_dir).realpath()
    logger.info('Loading plugins:')
    plugins_root = plugins_dir.parent if import_from_parent else plugins_dir
    if plugins_root not in sys.path:
        sys.path.insert(0, plugins_root)

    # Create an instance of each of the plugins, but set it to disabled
    e = PluginGlobals.env('microdrop.managed')
    initial_plugins = set(e.plugin_registry.values())
    imported_plugins = set()

    for package_i in plugins_dir.dirs():
        if package_i.isjunction() and not package_i.readlink().isdir():
            # Plugin directory is a junction/link to a non-existent target
            # path.
            logger.info('Skip import of `%s` (broken link to `%s`).',
                        package_i.name, package_i.readlink())
            continue
        elif package_i.name in (p.__module__.split('.')[0]
                                for p in initial_plugins):
            # Plugin with the same name has already been imported.
            logger.info('Skip import of `%s` (plugin with same name has '
                        'already been imported).', package_i.name)
            continue
        elif package_i.name.startswith('.'):
            logger.info('Skip import of hidden directory `%s`.',
                        package_i.name)
            continue

        try:
            plugin_module = package_i.name
            if package_i.joinpath('pyutilib.py').isfile():
                plugin_module = '.'.join([plugin_module, 'pyutilib'])
            if import_from_parent:
                plugin_module = '.'.join([plugins_dir.name, plugin_module])
            import_statement = 'import {}'.format(plugin_module)
            logger.debug(import_statement)
            exec(import_statement)
            all_plugins = set(e.plugin_registry.values())
            current_plugin = list(all_plugins - initial_plugins -
                                  imported_plugins)[0]
            logger.info('\t Imported: %s (%s)', current_plugin.__name__,
                        package_i)
            imported_plugins.add(current_plugin)
        except Exception:
            map(logger.info, traceback.format_exc().splitlines())
            logger.error('Error loading %s plugin.', package_i.name,
                         exc_info=True)

    # For each newly imported plugin class, create a service instance
    # initialized to the disabled state.
    new_plugins = []
    for class_ in imported_plugins:
        service = class_()
        service.disable()
        new_plugins.append(service)
    logger.debug('\t Created new plugin services: %s',
                 ','.join([p.__class__.__name__ for p in new_plugins]))
    return new_plugins


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
        raise KeyError('No plugin registered with name: %s' % name)
    return e.plugin_registry[name]


def get_service_instance_by_name(name, env='microdrop.managed'):
    '''
    Parameters
    ----------
    name : str
        Plugin name (e.g., ``microdrop.zmq_hub_plugin``).

        Corresponds to ``plugin_name`` key in plugin ``properties.yml`` file.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').

    Returns
    -------
    object
        Active service instance matching specified plugin name.

    Raises
    ------
    KeyError
        If no plugin is found registered with the specified name.
    '''
    e = PluginGlobals.env(env)
    plugins = [p for i, p in enumerate(e.services) if name == p.name]
    if plugins:
        return plugins[0]
    else:
        raise KeyError('No plugin registered with name: %s' % name)


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
    plugins = [p for i, p in enumerate(e.services)
               if name ==
               get_plugin_package_name(p.__class__.__module__.split('.')[0])]
    if plugins:
        return plugins[0]
    else:
        raise KeyError('No plugin registered with package name: %s' % name)


def get_plugin_package_name(module_name):
    '''
    Parameters
    ----------
    module_name : str
        Fully-qualified class name (e.g.,
        ``'plugins.dmf_control_board_plugin'``).

    Returns
    -------
    str
        Relative module name (e.g., ``'dmf_control_board_plugin'``)
    '''
    return module_name.split('.')[-1]


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
        List of plugin names (e.g., ``['microdrop.step_label_plugin', ...]``).
    '''
    e = PluginGlobals.env(env)
    service_names = []
    for name in get_plugin_names(env):
        plugin_class = e.plugin_registry[name]
        service = get_service_instance(plugin_class, env=env)
        if service is None:
            _L().warn('Plugin `%s` exists in registry, but instance cannot '
                      'be found.', name)
        else:
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
    logger = _L()  # use logger with function context

    # Query plugins for schedule requests for 'function'
    schedule_requests = {}
    for observer in observers.values():
        if hasattr(observer, 'get_schedule_requests'):
            schedule_requests[observer.name] =\
                    observer.get_schedule_requests(function)

    if schedule_requests:
        scheduler = task_scheduler.TaskScheduler(observers.keys())
        for request in [r for name, requests in schedule_requests.items()
                        for r in requests]:
            try:
                scheduler.request_order(*request)
            except AssertionError:
                logger.debug('Schedule requests for `%s`', function)
                map(logger.debug,
                    pprint.pformat(schedule_requests).splitlines())
                logger.info('emit_signal(%s) could not add schedule request '
                            '%s', function, request)
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


    .. versionchanged:: 2.20
        Log caller at info level, and log args and observers at debug level.
    '''
    logger = _L()  # use logger with function context
    i = 0
    caller = caller_name(skip=i)

    while not caller or caller == 'microdrop.plugin_manager.emit_signal':
        i += 1
        caller = caller_name(skip=i)

    try:
        observers = get_observers(function, interface)
        schedule = get_schedule(observers, function)

        return_codes = {}

        if args is None:
            args = []
        elif not isinstance(args, list):
            args = [args]

        if not any((name in caller) for name in ('logger', 'emit_signal')):
            logger.debug('caller: %s -> %s', caller, function)
            if logger.getEffectiveLevel() <= logging.DEBUG:
                logger.debug('args: (%s)', ', '.join(map(repr, args)))
        for observer_name in schedule:
            observer = observers[observer_name]
            try:
                f = getattr(observer, function)
                logger.debug('  call: %s.%s(...)', observer.name, function)
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
                    logger.error(message.getvalue().strip())
                map(logger.info, traceback.format_exc().splitlines())
        return return_codes
    except Exception, why:
        logger.error(why, exc_info=True)
        return {}


def enable(name, env='microdrop.managed'):
    '''
    Enable specified plugin.

    Parameters
    ----------
    name : str
        Plugin name (e.g., ``microdrop.zmq_hub_plugin``).

        Corresponds to ``plugin_name`` key in plugin ``properties.yml`` file.
    env : str, optional
        Name of ``pyutilib.component.core`` plugin environment (e.g.,
        ``'microdrop.managed``').
    '''
    service = get_service_instance_by_name(name, env)
    if not service.enabled():
        service.enable()
        _L().info('[PluginManager] Enabled plugin: %s', name)
    if hasattr(service, "on_plugin_enable"):
        service.on_plugin_enable()
    emit_signal('on_plugin_enabled', [env, service])


def disable(name, env='microdrop.managed'):
    '''
    Disable specified plugin.

    Parameters
    ----------
    name : str
        Plugin name (e.g., ``microdrop.zmq_hub_plugin``).

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


def connect_pyutilib_signal(signals, signal, *args, **kwargs):
    '''
    Connect pyutilib callbacks to corresponding signal in blinker namespace.

    Allows code to be written using blinker signals for easier testing outside
    of MicroDrop, while maintaining compatibility with pyutilib.

    Parameters
    ----------
    signals : blinker.Namespace
    signal : str
        Pyutilib signal name.
    *args, **kwargs
        Arguments passed to `pyutilib.component.core.ExtensionPoint()`

    Example
    -------

    >>> from microdrop.interfaces import IPlugin
    >>> import microdrop.app
    >>>
    >>> signals = blinker.Namespace()
    >>> signal = 'get_schedule_requests'
    >>> args = ('on_plugin_enable', )
    >>> connect_pyutilib_signal(signals, signal, IPlugin)
    >>> signals.signal(signal).send(*args)
    [(<bound method DmfDeviceController.get_schedule_requests of <Plugin DmfDeviceController 'microdrop.gui.dmf_device_controller'>>, [ScheduleRequest(before='microdrop.gui.config_controller', after='microdrop.gui.dmf_device_controller'), ScheduleRequest(before='microdrop.gui.main_window_controller', after='microdrop.gui.dmf_device_controller')])]
    '''
    import functools as ft
    import inspect

    from microdrop.plugin_manager import ExtensionPoint

    callbacks = [getattr(p, signal) for p in ExtensionPoint(*args, **kwargs) if hasattr(p, signal)]

    for callback_i in callbacks:
        if len(inspect.getargspec(callback_i)[0]) < 2:
            # Blinker signals require _at least_ one argument (assumed to be sender).
            # Wrap pyutilib signals without any arguments to make them work with blinker.
            @ft.wraps(callback_i)
            def _callback(*args, **kwargs):
                return callback_i()
        else:
            _callback = callback_i
        signals.signal(signal).connect(_callback, weak=False)


PluginGlobals.pop_env()
