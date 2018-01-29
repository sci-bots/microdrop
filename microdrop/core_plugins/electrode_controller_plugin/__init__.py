import logging
import pprint
import thread
import threading

from logging_helpers import _L
from pygtkhelpers.gthreads import gtk_threadsafe
from pyutilib.component.core import ExtensionPoint
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import gtk
import or_event
import pandas as pd
import zmq

from ...app_context import get_app, get_hub_uri
from ...interfaces import IElectrodeActuator
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
        _L().debug('%s', result)
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

    def set_channel_states(self, channel_states, save=True):
        '''
        .. versionadded:: X.X.X

        Set the state of multiple channels.

        Args:

            channel_states (pandas.Series) : State of channels, indexed by
                channel identifier (e.g., `37`).
            save (bool) : Trigger save request for protocol step.

        Returns:

            (dict) : States of modified channels and electrodes, as well as the
                total area of all actuated electrodes.
        '''
        app = get_app()

        # Resolve list of electrodes _and respective **channels**_ from channel
        # mapping in DMF device definition.
        channel_electrodes = (app.dmf_device.electrodes_by_channel
                              .ix[channel_states.index])
        electrode_states = pd.Series(channel_states
                                     .ix[channel_electrodes.index].values,
                                     index=channel_electrodes.values)
        logger = _L()  # use logger with method context
        if logger.getEffectiveLevel() <= logging.DEBUG:
            map(logger.debug, 'Translate channel states:\n%sto electrode '
                'states:\n%s' % (pprint.pformat(channel_electrodes),
                                 pprint.pformat(electrode_states))
                .splitlines())
        return self.set_electrode_states(electrode_states, save=save)

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
        logger = _L()  # use logger with method context

        # Resolve list of electrodes _and respective **channels**_ from channel
        # mapping in DMF device definition.
        result = self.get_state(electrode_states)

        # Set the state of DMF device channels.
        electrode_states = (result['electrode_states']
                            .combine_first(self.electrode_states))

        if save:
            self.electrode_states = electrode_states
            # def notify(step_number):
                # emit_signal('on_step_options_changed', [self.name,
                                                        # step_number],
                            # interface=IPlugin)
            # logger.info("emit_signal('on_step_options_changed')")
            # gtk.idle_add(notify, app.protocol.current_step_number)
        logger.debug('save=%s, electrode_states=%s', save, electrode_states)

        # Compute actuated area based on geometries in DMF device definition.
        result['actuated_area'] = self.get_actuated_area(electrode_states)
        if logger.isEnabledFor(logging.DEBUG):
            map(logger.debug, pprint.pformat(result).splitlines())
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
        self.step_cancelled = threading.Event()
        self._actuation_completed = threading.Event()
        self._electrodes_to_actuate = set()   # or `pandas.Series`?
        self._actuated_electrodes = set()   # or `pandas.Series`?

        self._watch_actuation_thread = None

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

        def _check_command_socket(wait_duration_s):
            '''
            Process each incoming message on the ZeroMQ plugin command socket.

            Stop listening if :attr:`stopped` event is set.
            '''
            self.plugin = ElectrodeControllerZmqPlugin(self, self.name,
                                                       get_hub_uri())
            # Initialize sockets.
            self.plugin.reset()

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
            thread = threading.Thread(target=_check_command_socket, args=(0.01,
                                                                          ),
                                      name=caller_name(0))
            thread.daemon = True
            thread.start()
            _L().debug('threads: %s' % threading.enumerate())

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
            _L().debug('Execute get_channel_states')
            self.plugin.execute_async('microdrop.electrode_controller_plugin',
                                      'get_channel_states')
        else:
            _L().debug('ZeroMQ plugin not ready.')

    def on_step_run(self):
        '''
        .. versionadded:: X.X.X

            1. Repeatedly emit ``get_actuation_request`` until no requests
               are received.
            2. Merge actuation states received in each round of requests and
               execute ZeroMQ ``set_electrode_states`` command accordingly.
            3. If any other plugins implement ``actuation_completed``, wait
               for ``actuation_completed`` signal before attempting next
               round of actuation requests.

        See `Issue #253`_ for more details.

        .. _`Issue #253`: https://github.com/sci-bots/microdrop/issues/253#issuecomment-360967363
        '''
        self.stop_step()

        while self._watch_actuation_thread is not None and not self._watch_actuation_thread.is_alive():
            pass

        def _wait_for_actuation_complete():
            # Clear step cancelled signal.
            self.step_cancelled.clear()

            _L().debug('thread started: %s', thread.get_ident())
            self._actuation_completed.clear()

            actuation_requests = None

            while actuation_requests is None or any(value_i is not None
                                                    for value_i in
                                                    actuation_requests
                                                    .itervalues()):
                actuation_requests = emit_signal('get_actuation_request')

                # Merge received actuation states from requests with
                # explicit states stored by this plugin.
                step_states = self.plugin.electrode_states.copy()

                for plugin_name_i, actuation_request_i in (actuation_requests
                                                           .iteritems()):
                    if actuation_request_i is not None:
                        _L().info('plugin: %s, actuation_request=%s',
                                  plugin_name_i, actuation_request_i)

                # Start with electrodes specified by this plugin.
                self._electrodes_to_actuate = \
                    set(pd.concat([step_states[step_states > 0]] +
                                  [actuation_request_i[actuation_request_i > 0]
                                   for actuation_request_i in
                                   actuation_requests.itervalues()
                                   if actuation_request_i is not None]).index
                        .tolist())
                self._actuated_electrodes = set()
                self._actuation_completed.clear()

                # Execute `set_electrode_states` command through ZeroMQ plugin
                # API to notify electrode actuator plugins (i.e., plugins
                # implementing the `IElectrodeActuator` interface) of the
                # electrodes to actuate.
                s_electrodes_to_actuate = \
                    pd.Series([True] * len(self._electrodes_to_actuate),
                              index=sorted(self._electrodes_to_actuate))

                if self.step_cancelled.is_set():
                    break

                _L().debug('s_electrodes_to_actuate=%s',
                           s_electrodes_to_actuate)
                self.plugin.execute('microdrop.electrode_controller_plugin',
                                    'set_electrode_states',
                                    electrode_states=s_electrodes_to_actuate,
                                    save=False)

                electrode_actuators = ExtensionPoint(IElectrodeActuator)
                if not electrode_actuators:
                    _L().info('No electrode actuators registered to actuate: '
                              '%s', self._electrodes_to_actuate)
                    self._actuation_completed.set()
                    continue
                else:
                    # Wait for `actuation_completed` signals indicating all
                    # specified electrodes have been actuated.
                    _L().info('waiting for the following electrodes to '
                              'complete actuation: %s',
                              self._electrodes_to_actuate -
                              self._actuated_electrodes)

                    # Wait/block until either:
                    #
                    #  1. `actuation_completed` signals have been received from
                    #     `IElectrodeActuator` plugins indicating all specified
                    #     electrodes have been actuated; OR
                    #  2. step has been cancelled.
                    event = or_event.OrEvent(self.step_cancelled,
                                             self._actuation_completed)
                    if event.wait():
                        if self._actuation_completed.is_set():
                            # Requested actuations were completed successfully.
                            _L().info('actuation completed (actuated '
                                      'channels:' '%s)',
                                      self._actuated_electrodes)
                        elif self.step_cancelled.is_set():
                            # Step was cancelled.
                            _L().info('Step was cancelled.')
                            gtk_threadsafe(lambda *args: emit_signal(*args) and
                                           False)('on_step_complete',
                                                  [self.name, 'Fail'])
                            break  # XXX Stop since step was cancelled.
            if not self.step_cancelled.is_set():
                gtk_threadsafe(lambda *args: emit_signal(*args) and
                               False)('on_step_complete', [self.name, None])
            _L().debug('thread finished: %s', thread.get_ident())
            self._watch_actuation_thread = None

        self._watch_actuation_thread = \
            threading.Thread(target=_wait_for_actuation_complete,
                             name='%s._wait_for_actuation_complete' %
                             caller_name(0))
        self._watch_actuation_thread.daemon = True  # Stop when app exits
        # Start watching for completed actuations.
        self._watch_actuation_thread.start()
        _L().debug('threads: %s' % threading.enumerate())

    def stop_step(self):
        # Cancel step (if running).
        self.step_cancelled.set()

    def on_step_complete(self, plugin_name, return_value):
        if return_value is not None:
            # Step did not complete as expected.  Stop executing current step.
            self.stop_step()

    def on_protocol_pause(self):
        """
        Handler called when a protocol is paused.
        """
        # Protocol was paused.  Stop executing current step.
        self.stop_step()

    def actuation_completed(self, plugin_name, actuated_electrodes):
        '''
        .. versionadded:: X.X.X

        Handle ``actuation_completed`` signal emitted by other plugins in
        response to ``set_electrode_states`` ZeroMQ once electrode actuation
        has completed.

        The ``actuation_completed``

        See `Issue #253`_ for more details.

        .. _`Issue #253`: https://github.com/sci-bots/microdrop/issues/253#issuecomment-360967363
        '''
        _L().debug('%s successfully actuated: %s', plugin_name,
                   actuated_electrodes)
        self._actuated_electrodes.update(actuated_electrodes)
        outstanding_actuations = (self._electrodes_to_actuate -
                                  self._actuated_electrodes)
        if not outstanding_actuations:
            _L().debug('all target electrodes successfully actuated')
            self._actuation_completed.set()
        else:
            _L().debug('still waiting on the following electrodes to be '
                       'actuated: %s', outstanding_actuations)


PluginGlobals.pop_env()
