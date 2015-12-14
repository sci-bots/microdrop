"""
Copyright 2015 Christian Fobel

This file is part of monitor_plugin.

monitor_plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with monitor_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""
import warnings

import zmq
from path_helpers import path
from flatland import Form, String
from microdrop.plugin_helpers import AppDataController, get_plugin_info
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements)


PluginGlobals.push_env('microdrop.managed')


class Notifier(object):
    def __init__(self, uri):
        self.context = zmq.Context.instance()
        self.pub_socket = zmq.Socket(self.context, zmq.PUB)
        self.pub_socket.bind(uri)

    def notify(self, *args, **kwargs):
        '''
        Send notification, issuing warnings on encountered exceptions by
        default.

        Args:

            on_error (function) : Custom exception handler function, accepting
                exception as single argument.
        '''
        #
        on_error = kwargs.pop('on_error', None)

        try:
            self.pub_socket.send_pyobj(*args)
        except (Exception, ), exception:
            if on_error is None:
                warnings.warn(str(exception))
            else:
                on_error(exception)


class MonitorPlugin(Plugin, AppDataController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    version = get_plugin_info(path(__file__).parent).version
    plugin_name = get_plugin_info(path(__file__).parent).plugin_name

    '''
    AppFields
    ---------

    A flatland Form specifying application options for the current plugin.
    Note that nested Form objects are not supported.

    Since we subclassed AppDataController, an API is available to access and
    modify these attributes.  This API also provides some nice features
    automatically:
        -all fields listed here will be included in the app options dialog
            (unless properties=dict(show_in_gui=False) is used)
        -the values of these fields will be stored persistently in the microdrop
            config file, in a section named after this plugin's name attribute
    '''
    AppFields = Form.of(
        String.named('publish_uri').using(optional=True, default=''),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.notifier = None

    def verify_connected(self):
        if self.notifier is None:
            app_values = self.get_app_values()
            if 'publish_uri' in app_values and app_values['publish_uri']:
                self.notifier = Notifier(app_values['publish_uri'])
            else:
                return False
        return True

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        return []

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        if self.notifier is not None:
            del self.notifier

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.

        Note: if you inherit your plugin from AppDataController and don't
        implement this handler, by default, it will automatically load all
        app options from the config file. If you decide to overide the
        default handler, you should call:

            AppDataController.on_plugin_enable(self)

        to retain this functionality.
        """
        self.verify_connected()
        super(MonitorPlugin, self).on_plugin_enable()

    def on_app_exit(self):
        """
        Handler called just before the Microdrop application exits.
        """
        if self.notifier is not None:
            self.notifier.notify({'signal': 'on_app_exit'})

    def on_protocol_swapped(self, old_protocol, protocol):
        """
        Handler called when a different protocol is swapped in (e.g., when
        a protocol is loaded or a new protocol is created).
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_protocol_swapped',
                                  'data': {'old_protocol': old_protocol,
                                           'protocol': protocol}})

    def on_protocol_changed(self):
        """
        Handler called when a protocol is modified.
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_protocol_changed', 'data': {}})

    def on_protocol_run(self):
        """
        Handler called when a protocol starts running.
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_protocol_run', 'data': {}})

    def on_protocol_pause(self):
        """
        Handler called when a protocol is paused.
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_protocol_pause', 'data': {}})

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        """
        Handler called when a different DMF device is swapped in (e.g., when
        a new device is loaded).
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_protocol_swapped',
                                  'data': {'old_dmf_device': old_dmf_device,
                                           'dmf_device': dmf_device}})

    def on_dmf_device_changed(self):
        """
        Handler called when a DMF device is modified (e.g., channel
        assignment, scaling, etc.). This signal is also sent when a new
        device is imported or loaded from outside of the main device
        directory.
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_dmf_device_changed',
                                  'data': {}})

    def on_experiment_log_changed(self, experiment_log):
        """
        Handler called when the current experiment log changes (e.g., when a
        protocol finishes running.
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_experiment_log_changed',
                                  'data': {'experiment_log': experiment_log}})

    def on_experiment_log_selection_changed(self, data):
        """
        Handler called whenever the experiment log selection changes.

        Parameters:
            data : experiment log data (list of dictionaries, one per step)
                for the selected steps
        """
        if self.verify_connected():
            self.notifier.notify({'signal':
                                  'on_experiment_log_selection_changed',
                                  'data': {'data': data}})

    def on_app_options_changed(self, plugin_name):
        """
        Handler called when the app options are changed for a particular
        plugin.  This will, for example, allow for GUI elements to be
        updated.

        Parameters:
            plugin : plugin name for which the app options changed
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_app_options_changed',
                                  'data': {'plugin_name': plugin_name}})

    def on_step_options_changed(self, plugin, step_number):
        """
        Handler called when the step options are changed for a particular
        plugin.  This will, for example, allow for GUI elements to be
        updated based on step specified.

        Parameters:
            plugin : plugin instance for which the step options changed
            step_number : step number that the options changed for
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_step_options_changed',
                                  'data': {'plugin': plugin,
                                           'step_number': step_number}})

    def on_step_options_swapped(self, plugin, old_step_number, step_number):
        """
        Handler called when the step options are changed for a particular
        plugin.  This will, for example, allow for GUI elements to be
        updated based on step specified.

        Parameters:
            plugin : plugin instance for which the step options changed
            step_number : step number that the options changed for
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_step_options_swapped',
                                  'data': {'plugin': plugin,
                                           'old_step_number': old_step_number,
                                           'step_number': step_number}})

    def on_step_swapped(self, old_step_number, step_number):
        """
        Handler called when the current step is swapped.
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_step_swapped',
                                  'data': {'old_step_number': old_step_number,
                                           'step_number': step_number}})

    def on_step_run(self):
        """
        Handler called whenever a step is executed. Note that this signal
        is only emitted in realtime mode or if a protocol is running.

        Plugins that handle this signal must emit the on_step_complete
        signal once they have completed the step. The protocol controller
        will wait until all plugins have completed the current step before
        proceeding.

        return_value can be one of:
            None
            'Repeat' - repeat the step
            or 'Fail' - unrecoverable error (stop the protocol)
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_step_run', 'data': {}})

    def on_step_complete(self, plugin_name, return_value=None):
        """
        Handler called whenever a plugin completes a step.

        return_value can be one of:
            None
            'Repeat' - repeat the step
            or 'Fail' - unrecoverable error (stop the protocol)
        """
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_experiment_log_changed',
                                  'data': {}})

    def on_step_created(self, step_number):
        if self.verify_connected():
            self.notifier.notify({'signal': 'on_step_created',
                                  'data': {'step_number': step_number}})


PluginGlobals.pop_env()
