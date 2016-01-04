"""
Copyright 2015 Christian Fobel

This file is part of electrode_controller_plugin.

electrode_controller_plugin is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your option)
any later version.

electrode_controller_plugin is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License
along with electrode_controller_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""
import logging

from flatland import Form, String
from microdrop.app_context import get_app
from microdrop.plugin_helpers import (AppDataController, StepOptionsController,
                                      get_plugin_info)
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      ScheduleRequest, implements, emit_signal,
                                      get_service_instance_by_name)
from path_helpers import path
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import gobject
import gtk
import pandas as pd
import zmq

logger = logging.getLogger(__name__)


class ElectrodeControllerZmqPlugin(ZmqPlugin):
    '''
    API for turning electrode(s) on/off.

    Must handle:
     - Updating state of hardware channels (if connected).
     - Updating device user interface.
    '''
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.control_board = None
        super(ElectrodeControllerZmqPlugin, self).__init__(*args, **kwargs)

    @property
    def electrode_states(self):
        # Set the state of DMF device channels.
        step_options = self.parent.get_step_options()
        return step_options.get('electrode_states', pd.Series())

    @electrode_states.setter
    def electrode_states(self, electrode_states):
        # Set the state of DMF device channels.
        step_options = self.parent.get_step_options()
        step_options['electrode_states'] = electrode_states

    def get_actuated_area(self, electrode_states):
        '''
        Get area of actuated electrodes.
        '''
        app = get_app()
        actuated_electrodes = electrode_states[electrode_states > 0].index
        return app.dmf_device.electrode_areas.ix[actuated_electrodes].sum()

    def get_state(self, electrode_states):
        app = get_app()

        electrode_channels = (app.dmf_device.actuated_channels(electrode_states
                                                               .index))
        channel_states = pd.Series(electrode_states.values,
                                   index=electrode_channels)
        return {'electrode_states': electrode_states,
                'channel_states': channel_states}

    def get_channel_states(self):
        '''
        Returns:

            (pandas.Series) : State of channels, indexed by channel.
        '''
        result = self.get_state(self.electrode_states)
        result['actuated_area'] = self.get_actuated_area(result
                                                         ['electrode_states'])
        return result

    def set_electrode_state(self, electrode_id, state):
        '''
        Set the state of a single electrode.

        Args:

            electrode_id (str) : Electrode identifier (e.g., `"electrode001"`)
            state (int) : State of electrode
        '''
        return self.set_electrode_states(pd.Series([state],
                                                   index=[electrode_id]))

    def set_electrode_states(self, electrode_states):
        '''
        Set the state of multiple electrodes.

        Args:

            electrode_states (pandas.Series) : State of electrodes, indexed by
                electrode identifier (e.g., `"electrode001"`).

        Returns:

            (dict) : States of modified channels and electrodes, as well as the
                total area of all actuated electrodes.
        '''
        app = get_app()

        # Set the state of DMF device channels.
        self.electrode_states = (electrode_states
                                 .combine_first(self.electrode_states))

        def notify(step_number):
            emit_signal('on_step_options_changed', [self.name, step_number],
                        interface=IPlugin)
        gtk.idle_add(notify, app.protocol.current_step_number)

        result = self.get_state(electrode_states)
        result['actuated_area'] = self.get_actuated_area(self.electrode_states)
        return result

    def on_execute__set_electrode_state(self, request):
        data = decode_content_data(request)
        return self.set_electrode_state(data['electrode_id'], data['state'])

    def on_execute__set_electrode_states(self, request):
        data = decode_content_data(request)
        try:
            return self.set_electrode_states(data['electrode_states'])
        except:
            logger.error(str(data), exc_info=True)

    def on_execute__get_channel_states(self, request):
        return self.get_channel_states()

PluginGlobals.push_env('microdrop.managed')


class ElectrodeControllerPlugin(Plugin, AppDataController,
                                StepOptionsController):
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
        String.named('hub_uri').using(optional=True,
                                      default='tcp://localhost:31000'),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.command_timeout_id = None

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('wheelerlab.zmq_hub_plugin', self.name)]
        else:
            return []

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
        super(ElectrodeControllerPlugin, self).on_plugin_enable()
        app_values = self.get_app_values()

        self.cleanup()
        self.plugin = ElectrodeControllerZmqPlugin(self, self.name,
                                                   app_values['hub_uri'])
        # Initialize sockets.
        self.plugin.reset()

        def check_command_socket():
            try:
                msg_frames = (self.plugin.command_socket
                              .recv_multipart(zmq.NOBLOCK))
            except zmq.Again:
                pass
            else:
                self.plugin.on_command_recv(msg_frames)
            return True

        self.command_timeout_id = gobject.timeout_add(10, check_command_socket)

    def cleanup(self):
        if self.command_timeout_id is not None:
            gobject.source_remove(self.command_timeout_id)
        if self.plugin is not None:
            self.plugin = None

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        self.cleanup()

    def on_app_exit(self):
        """
        Handler called just before the Microdrop application exits.
        """
        self.cleanup()

    def on_step_swapped(self, old_step_number, step_number):
        if self.plugin is not None:
            self.plugin.execute_async('wheelerlab.electrode_controller_plugin',
                                      'get_channel_states')


PluginGlobals.pop_env()
