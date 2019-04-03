'''
.. versionchanged:: 2.32.1
    Remove experiment log window.
'''
import os

from .. import __version__
from ..app_context import get_app
from ..experiment_log import ExperimentLog
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, emit_signal, ScheduleRequest,
                              get_service_names, get_service_instance_by_name)
from .dmf_device_controller import DEVICE_FILENAME


PluginGlobals.push_env('microdrop')


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
        '''
        .. versionchanged:: 2.28.1
            Do not create a new experiment after saving experiment log.
        '''
        self.save(create_new=False)

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        '''
        .. versionchanged:: 2.32.2
            Removed method.

        .. versionchanged:: X.X.X
            Restored method since it is necessary to initialize an experiment
            log directory.
        '''
        app = get_app()
        if dmf_device and dmf_device.name:
            device_path = os.path.join(app.get_device_directory(),
                                       dmf_device.name, "logs")
            experiment_log = ExperimentLog(device_path)
            emit_signal("on_experiment_log_changed", experiment_log)

    def save(self, create_new=True):
        '''
        .. versionchanged:: 2.28.1
            Add :data:`create_new` parameter.

        .. versionchanged:: 2.32.1
            Save log directory if directory is not empty.

        Parameters
        ----------
        create_new : bool, optional
            Create new experiment log after saving current log.
        '''
        app = get_app()

        # Only save the current log if it is not empty (i.e., directory is not
        # empty).
        if (hasattr(app, 'experiment_log') and app.experiment_log and
                app.experiment_log.get_log_path().listdir()):
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

            if create_new:
                # create a new log
                experiment_log = ExperimentLog(app.experiment_log.directory)
                emit_signal('on_experiment_log_changed', experiment_log)

                # disable new experiment menu until a step has been run (i.e., until
                # we have some data in the log)
                self.menu_new_experiment.set_sensitive(False)

    ###########################################################################
    # Accessor methods
    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_experiment_log_changed':
            # ensure that the app's reference to the new experiment log gets set
            return [ScheduleRequest('microdrop.app', self.name)]
        return []

PluginGlobals.pop_env()
