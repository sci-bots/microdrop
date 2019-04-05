'''
.. versionchanged:: 2.32.1
    Remove experiment log window.
'''
from functools import wraps
import os

from logging_helpers import _L
from pygtkhelpers.gthreads import gtk_threadsafe
from pygtkhelpers.ui.extra_dialogs import yesno
import gtk

from .. import __version__
from ..app_context import get_app
from ..experiment_log import ExperimentLog
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, emit_signal, ScheduleRequest,
                              get_service_names, get_service_instance_by_name)
from .dmf_device_controller import DEVICE_FILENAME


PluginGlobals.push_env('microdrop')


def require_experiment_log(log_level='info'):
    '''Decorator factory to require experiment log.

    Parameters
    ----------
    log_level : str
        Level to log message to if DropBot is not connect.

    Returns
    -------
    function
        Decorator to require experiment log.


    .. versionadded:: 2.32.3
    '''
    def _require_experiment_log(func):
        @wraps(func)
        def _wrapped(*args, **kwargs):
            app = get_app()
            if not getattr(app, 'experiment_log', None):
                logger = _L()
                log_func = getattr(logger, log_level)
                log_func('No active experiment log.')
            else:
                return func(*args, **kwargs)
        return _wrapped
    return _require_experiment_log


class ExperimentLogController(SingletonPlugin):
    '''
    .. versionchanged:: 2.21
        Read glade file using ``pkgutil`` to also support loading from ``.zip``
        files (e.g., in app packaged with Py2Exe).
    '''
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.experiment_log_controller"

    ###########################################################################
    # Callback methods
    def on_app_exit(self):
        '''Save experiment info to log directory.


        .. versionchanged:: 2.28.1
            Do not create a new experiment after saving experiment log.
        '''
        self.save()

    @require_experiment_log()
    def on_new_experiment(self, widget=None, data=None):
        '''Save current experiment info and create new experiment.


        .. versionchanged:: 2.32.3
            Use :meth:`create()` method to create new log directory.
        '''
        _L().debug('New experiment clicked')
        self.save()
        app = get_app()
        self.create(app.experiment_log.directory)

    def on_plugin_enable(self):
        '''Register ``File > New Experiment`` callback; disable on app start.


        .. versionadded:: 2.32.3
        '''
        app = get_app()
        app.experiment_log_controller = self
        self.menu_new_experiment = app.builder.get_object('menu_new_experiment')
        app.signals["on_menu_new_experiment_activate"] = self.on_new_experiment
        self.menu_new_experiment.set_sensitive(False)

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        '''
        .. versionchanged:: 2.32.2
            Removed method.

        .. versionchanged:: 2.32.3
            Restored method since it is necessary to initialize an experiment
            log directory.  Save experiment info (if available) before creating
            new experiment log.
        '''
        if dmf_device and dmf_device.name:
            app = get_app()
            device_path = os.path.join(app.get_device_directory(),
                                       dmf_device.name, "logs")
            self.save()
            self.create(device_path)

    @require_experiment_log()
    def on_protocol_finished(self):
        '''Save experiment info to log directory; optionally create new log.


        .. versionchanged:: 2.32.3
            Use :meth:`create()` method to create new log directory.
        '''
        self.save()

        @gtk_threadsafe
        def ask_create_new():
            self.menu_new_experiment.set_sensitive(True)

            result = yesno('Experiment complete. Would you like to start a new'
                           ' experiment?')
            if result == gtk.RESPONSE_YES:
                app = get_app()
                self.create(app.experiment_log.directory)

        app = get_app()
        if not app.experiment_log.empty:
            ask_create_new()

    @require_experiment_log()
    def save(self):
        '''Save experiment info to current log working directory.

        The ``app.experiment_log`` allows plugins to append arbitrary data
        objects to a list using the ``add_data()`` method.  Until *this* method
        is called, the experiment log data is only stored in-memory.

        This method performs the following actions::

         1. Append experiment metadata to the experiment log data list,
            including MicroDrop version, device name, protocol name, and plugin
            versions.
         2. Save in-memory experiment log data to disk in the current log
            working directory.
         3. Write a copy of the active protocol to disk in the current log
            working directory.
         4. Write a copy of the active device SVG to disk in the current log
            working directory.

        Note that steps **2**-**4** will overwrite the respective files if they
        already in the current log working directory.


        .. versionchanged:: 2.28.1
            Add :data:`create_new` parameter.

        .. versionchanged:: 2.32.1
            Save log directory if directory is not empty.
        '''
        app = get_app()
        if app.experiment_log.empty:
            # Experiment log is empty, so do nothing.
            return

        data = {'software version': __version__}
        data['device name'] = app.dmf_device.name
        data['protocol name'] = app.protocol.name
        plugin_versions = {}
        for name in get_service_names(env='microdrop.managed'):
            service = get_service_instance_by_name(name)
            if service._enable:
                plugin_versions[name] = str(service.version)
        data['plugins'] = plugin_versions
        app.experiment_log.add_data(data)
        log_path = app.experiment_log.save()

        # Save the protocol to experiment log directory.
        app.protocol.save(os.path.join(log_path, 'protocol'))

        # Convert device to SVG string.
        svg_unicode = app.dmf_device.to_svg()
        # Save the device to experiment log directory.
        with open(os.path.join(log_path, DEVICE_FILENAME), 'wb') as output:
            output.write(svg_unicode)

    def create(self, directory):
        '''Create a new experiment log with corresponding log directory.

        .. versionadded:: 2.32.3
        '''
        experiment_log = ExperimentLog(directory)
        emit_signal('on_experiment_log_changed', experiment_log)

    ###########################################################################
    # Accessor methods
    def get_schedule_requests(self, function_name):
        '''Request scheduling of certain signals relative to other plugins.


        .. versionchanged:: 2.32.3
            Request scheduling of ``on_plugin_enable`` handling after main
            window controller to ensure GTK builder reference is ready.
        '''
        if function_name == 'on_experiment_log_changed':
            # Ensure that the app's reference to the new experiment log gets
            # set.
            return [ScheduleRequest('microdrop.app', self.name)]
        elif function_name == 'on_plugin_enable':
            # Ensure that the app's GTK builder is initialized.
            return [ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        return []

PluginGlobals.pop_env()
