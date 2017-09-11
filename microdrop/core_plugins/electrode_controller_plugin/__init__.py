import logging
import threading

from pygtkhelpers.gthreads import gtk_threadsafe
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import gtk
import pandas as pd
import zmq

from ...app_context import get_app, get_hub_uri
from ...plugin_helpers import StepOptionsController
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements, emit_signal)

logger = logging.getLogger(__name__)


def drop_duplicates_by_index(series):
    '''
    Drop all but first entry for each set of entries with the same index value.

    Args:

        series (pandas.Series) : Input series.

    Returns:

        (pandas.Series) : Input series with *first* value in `series` for each
            *distinct* index value (i.e., duplicate entries dropped for same
            index value).
    '''
    return series[~series.index.duplicated()]


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

        electrode_channels = (app.dmf_device
                              .actuated_channels(electrode_states.index)
                              .dropna().astype(int))

        # Each channel should be represented *at most* once in
        # `channel_states`.
        channel_states = pd.Series(electrode_states
                                   .ix[electrode_channels.index].values,
                                   index=electrode_channels)
        # Duplicate entries may result from multiple electrodes mapped to the
        # same channel or vice versa.
        channel_states = drop_duplicates_by_index(channel_states)

        channel_electrodes = (app.dmf_device.electrodes_by_channel
                              .ix[channel_states.index])
        electrode_states = pd.Series(channel_states
                                     .ix[channel_electrodes.index].values,
                                     index=channel_electrodes.values)

        # Each electrode should be represented *at most* once in
        # `electrode_states`.
        return {'electrode_states': drop_duplicates_by_index(electrode_states),
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

    def set_electrode_states(self, electrode_states, save=True):
        '''
        Set the state of multiple electrodes.

        Args:

            electrode_states (pandas.Series) : State of electrodes, indexed by
                electrode identifier (e.g., `"electrode001"`).
            save (bool) : Trigger save request for protocol step.

        Returns:

            (dict) : States of modified channels and electrodes, as well as the
                total area of all actuated electrodes.
        '''
        app = get_app()

        result = self.get_state(electrode_states)

        # Set the state of DMF device channels.
        self.electrode_states = (result['electrode_states']
                                 .combine_first(self.electrode_states))

        if save:
            def notify(step_number):
                emit_signal('on_step_options_changed', [self.name,
                                                        step_number],
                            interface=IPlugin)
            gtk.idle_add(notify, app.protocol.current_step_number)

        result['actuated_area'] = self.get_actuated_area(self.electrode_states)
        return result

    def on_execute__set_electrode_state(self, request):
        data = decode_content_data(request)
        return self.set_electrode_state(data['electrode_id'], data['state'])

    def on_execute__set_electrode_states(self, request):
        data = decode_content_data(request)
        try:
            return self.set_electrode_states(data['electrode_states'],
                                             save=data.get('save', True))
        except Exception:
            logger.error(str(data), exc_info=True)

    def on_execute__get_channel_states(self, request):
        return self.get_channel_states()


PluginGlobals.push_env('microdrop')


class ElectrodeControllerPlugin(SingletonPlugin, StepOptionsController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    plugin_name = 'microdrop.electrode_controller_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.stopped = threading.Event()

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.

        Note: if you inherit your plugin from AppDataController and don't
        implement this handler, by default, it will automatically load all
        app options from the config file. If you decide to overide the
        default handler, you should call:

            AppDataController.on_plugin_enable(self)

        to retain this functionality.

        .. versionchanged:: 2.11.2
            Launch background thread to monitor plugin ZeroMQ command socket.

            Use :func:`gtk_threadsafe` decorator to wrap thread-related code
            to ensure GTK/GDK are initialized properly for a threaded
            application.
        """
        self.cleanup()
        self.plugin = ElectrodeControllerZmqPlugin(self, self.name,
                                                   get_hub_uri())
        # Initialize sockets.
        self.plugin.reset()

        def _check_command_socket(wait_duration_s):
            '''
            Process each incoming message on the ZeroMQ plugin command socket.

            Stop listening if :attr:`stopped` event is set.
            '''
            self.stopped.clear()
            while not self.stopped.wait(wait_duration_s):
                try:
                    msg_frames = (self.plugin.command_socket
                                  .recv_multipart(zmq.NOBLOCK))
                except zmq.Again:
                    pass
                else:
                    self.plugin.on_command_recv(msg_frames)

        @gtk_threadsafe
        def _launch_socket_monitor_thread():
            '''
            Launch background thread to monitor plugin ZeroMQ command socket.
            '''
            thread = threading.Thread(target=_check_command_socket,
                                      args=(0.01, ))
            thread.daemon = True
            thread.start()

        _launch_socket_monitor_thread()

    def cleanup(self):
        self.stopped.set()
        if self.plugin is not None:
            self.plugin = None

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        self.cleanup()

    def on_app_exit(self):
        """
        Handler called just before the MicroDrop application exits.
        """
        self.cleanup()

    def on_step_swapped(self, old_step_number, step_number):
        if self.plugin is not None:
            self.plugin.execute_async('microdrop.electrode_controller_plugin',
                                      'get_channel_states')


PluginGlobals.pop_env()
