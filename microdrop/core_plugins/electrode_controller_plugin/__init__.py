from __future__ import division, print_function, unicode_literals
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import functools as ft
import logging
import pprint
import threading

from flatland import Float, Form
from flatland.validation import ValueAtLeast
from logging_helpers import _L, caller_name
from pygtkhelpers.gthreads import gtk_threadsafe
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import pandas as pd
import si_prefix as si
import trollius as asyncio
import zmq

from ...app_context import (get_app, get_hub_uri, MODE_RUNNING_MASK,
                            MODE_REAL_TIME_MASK)
from ...interfaces import (IApplicationMode, IElectrodeController)
from ...plugin_helpers import (StepOptionsController, AppDataController,
                               hub_execute, hub_execute_async)
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements, ScheduleRequest)

logger = logging.getLogger(__name__)


@asyncio.coroutine
def _warning(signal, message, **kwargs):
    '''
    .. versionadded:: X.X.X

    Send warning signal and gather response from receivers.

    If no receivers are available or any receiver raises an exception, raise
    the specified warning message as a `RuntimeError`.

    Raises
    ------
    RuntimeError
        If no receivers are available or any receiver raises an exception.
    '''
    responses = signal.send(message, **kwargs)

    try:
        receivers, co_callbacks = zip(*responses)
        results = yield asyncio.From(asyncio.gather(*co_callbacks))
    except Exception:
        raise RuntimeError(message)
    else:
        raise asyncio.Return(zip(receivers, results))


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


class ElectrodeControllerZmqPlugin(ZmqPlugin, StepOptionsController):
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
        '''
        .. versionchanged:: 2.25
            Call :meth:`parent.set_step_values()` to signal changed options.
            Also, only store states for electrodes that are actuated.

        .. versionchanged:: 2.28.3
            Ensure each electrode has _at most_ one state represented in
            :data:`electrode_states` (remove any duplicates).
        '''
        # Set the state of DMF device channels.
        step_options = self.parent.get_step_options()
        step_options['electrode_states'] = \
            drop_duplicates_by_index(electrode_states[electrode_states > 0])
        gtk_threadsafe(self.parent.set_step_values)(step_options)

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
        .. versionadded:: 2.25

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
        logger.debug('save=%s, electrode_states=%s', save, electrode_states)

        # Compute actuated area based on geometries in DMF device definition.
        result['actuated_area'] = self.get_actuated_area(electrode_states)
        if logger.isEnabledFor(logging.DEBUG):
            map(logger.debug, pprint.pformat(result).splitlines())
        return result

    def on_execute__set_dynamic_electrode_states(self, request):
        data = decode_content_data(request)
        return data['electrode_states']

    def on_execute__set_electrode_state(self, request):
        data = decode_content_data(request)
        return self.set_electrode_state(data['electrode_id'], data['state'])

    def on_execute__set_electrode_states(self, request):
        '''
        .. versionchanged:: 2.28.3
            Log error traceback to debug level.
        '''
        data = decode_content_data(request)
        try:
            return self.set_electrode_states(data['electrode_states'],
                                             save=data.get('save', True))
        except Exception:
            logger = _L()  # use logger with method context
            logger.debug(str(data), exc_info=True)
            gtk_threadsafe(ft.partial(logger.error, str(data)))()

    def on_execute__set_electrode_direction_states(self, request):
        '''
        .. versionadded:: 2.28

        Turn on static state of neighbour electrodes in specified direction;
        turning off existing corresponding electrode state.

        If no neighbour exists in the specified direction for an electrode,
        leave the current state unchanged.


        .. versionchanged:: 2.28.3
            Log error traceback to debug level.
        '''
        data = decode_content_data(request)
        try:
            direction = data['direction']
            app = get_app()
            electrode_states = self.electrode_states.copy()
            neighbours = (app.dmf_device.electrode_neighbours
                          .loc[electrode_states.index, direction].dropna())

            # For electrodes with a neighbour in the specified direction:
            #  - Turn off current electrode state.
            electrode_states.loc[neighbours.index] = 0
            #  - Turn on neighbour electrode state.
            neighbour_states = pd.Series(1, index=neighbours.values)

            self.electrode_states = electrode_states.append(neighbour_states)
        except Exception:
            logger = _L()  # use logger with method context
            logger.debug(str(data), exc_info=True)
            gtk_threadsafe(ft.partial(logger.error, str(data)))()

    def on_execute__get_channel_states(self, request):
        return self.get_channel_states()

    def on_execute__clear_electrode_states(self, request):
        self.electrode_states = pd.Series()


PluginGlobals.push_env('microdrop')


class ElectrodeControllerPlugin(SingletonPlugin, StepOptionsController,
                                AppDataController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    implements(IApplicationMode)
    implements(IElectrodeController)
    implements(IApplicationMode)
    plugin_name = 'microdrop.electrode_controller_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.stopped = threading.Event()
        self._active_actuation = None
        self.executor = ThreadPoolExecutor(max_workers=1)

    @property
    def AppFields(self):
        '''
        .. versionadded:: 2.25
        '''
        return Form.of(
            Float.named('default_duration').using(default=1., optional=True),
            Float.named('default_voltage').using(default=100, optional=True),
            Float.named('default_frequency').using(default=10e3,
                                                   optional=True))

    @property
    def StepFields(self):
        """
        Dynamically generate step fields to support dynamic default values.


        .. versionadded:: 2.25

        .. versionchanged:: 2.28.2
            Set explicit field titles to prevent case mangling for protocol
            grid column titles.
        """
        app_values = self.get_app_values()
        if not app_values:
            app_values = self.get_default_app_options()
            self.set_app_values(app_values)

        fields = Form.of(Float.named('Duration (s)')
                         .using(default=app_values['default_duration'],
                                optional=True,
                                validators=[ValueAtLeast(minimum=0)]),
                         Float.named('Voltage (V)')
                         .using(default=app_values['default_voltage'],
                                optional=True,
                                validators=[ValueAtLeast(minimum=0)]),
                         Float.named('Frequency (Hz)')
                         .using(default=app_values['default_frequency'],
                                optional=True,
                                validators=[ValueAtLeast(minimum=0)]))

        # Set explicit field title to prevent case mangling for protocol grid
        # column titles.
        for field in fields.field_schema:
            field.properties['title'] = field.name
        return fields

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

        .. versionchanged:: 2.25
            Register ``"Clear _all electrode states"`` command with command
            plugin.
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

        hub_execute('microdrop.command_plugin', 'register_command',
                    command_name='clear_electrode_states',
                    namespace='global', plugin_name=self.name,
                    title='Clear _all electrode states')

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
        '''
        .. versionchanged:: 2.25
            Use `hub_execute_async()` to send `get_channels_states()` request
            to ZeroMQ plugin interface to ensure thread-safety.
        '''
        if self.plugin is not None:
            _L().debug('Execute get_channel_states')
            hub_execute_async(self.name, 'get_channel_states')
        else:
            _L().debug('ZeroMQ plugin not ready.')

    @asyncio.coroutine
    def execute_actuation(self, signals, static_states, dynamic_states,
                          voltage, frequency, duration_s):
        '''
        .. versionadded:: 2.25


        XXX Coroutine XXX

        Execute specified *static* and *dynamic* electrode actuations.

        Parameters
        ----------
        signals : blinker.Namespace
            Signals namespace.

            .. versionadded:: X.X.X
        static_states : pandas.Series
            Static electrode actuation states, indexed by electrode ID, (e.g.,
            `"electrode001"`).
        dynamic_states : pandas.Series
            Dynamic electrode actuation states, indexed by electrode ID.
        voltage : float
            Actuation amplitude as RMS AC voltage (in volts).

            .. versionadded:: X.X.X
        frequency : float
            Actuation frequency (in Hz).

            .. versionadded:: X.X.X
        duration_s : float
            Actuation duration (in seconds).  If not specified, use value from
            step options.

        Returns
        -------
        dict
            Response with fields:

            - ``start``: actuation start timestamp (`datetime.datetime`).
            - ``end``: actuation start timestamp (`datetime.datetime`).
            - ``actuated_electrodes``: actuated electrode IDs (`list`).

        See Also
        --------
        execute_actuations


        .. versionchanged:: 2.25
            Still apply for specified duration even if _no electrodes_ are
            specified for actuation.

        .. versionchanged:: 2.28.2
            Allow user to optionally ignore failed actuations.

        .. versionchanged:: X.X.X
            Add `signals`, `voltage` and `frequency` parameters.  Refactor the
            to set waveform parameters using ``signals`` namespace instead.

        .. versionchanged:: X.X.X
            Refactor electrode actuation requests to use :data:`signals`
            interface instead of using pyutilib :func:`emit_signal()`.
        '''
        # Notify other ZMQ plugins that `dynamic_electrodes_states` have
        # changed.

        try:
            hub_execute_async(self.name, 'set_dynamic_electrode_states',
                              electrode_states=dynamic_states)
        except Exception as exception:
            _L().debug(str(exception), exc_info=True)

        static_electrodes_to_actuate = set(static_states[static_states >
                                                         0].index)
        dynamic_electrodes_to_actuate = set(dynamic_states[dynamic_states >
                                                           0].index)

        electrodes_to_actuate = (dynamic_electrodes_to_actuate |
                                 static_electrodes_to_actuate)

        # Execute `set_electrode_states` command through ZeroMQ plugin
        # API to notify electrode actuator plugins (i.e., plugins
        # implementing the `IElectrodeActuator` interface) of the
        # electrodes to actuate.
        s_electrodes_to_actuate = \
            pd.Series(True, index=sorted(electrodes_to_actuate))

        @asyncio.coroutine
        def set_waveform(key, value):
            exception = None
            result = signals.signal('set-%s' % key).send(value)
            if result:
                try:
                    receivers, co_callbacks = zip(*result)
                    if receivers:
                        results = yield asyncio.From(asyncio
                                                     .gather(*co_callbacks))
                except Exception as exception:
                    pass
                else:
                    if receivers:
                        raise asyncio.Return(zip(receivers, results))

            if exception is not None:
                message = ('Error setting **%s**: `%s`' % (key, exception))
            else:
                message = ('No waveform generators available to set **%s**.' %
                           key)

            yield asyncio.From(_warning(signals.signal('warning'), message,
                                        title='Warning: failed to set %s' %
                                        key, key='waveform-%s' % key))

        for key, value, unit in (('frequency', frequency, 'Hz'),
                                 ('voltage', voltage, 'V')):
            waveform_result = yield asyncio.From(set_waveform(key, value))

            if waveform_result:
                _L().info('%s set to %s%s (receivers: `%s`)', key,
                          si.si_format(value), unit, zip(*waveform_result)[0])

        electrode_actuators = signals.signal('on-actuation-request')\
            .send(s_electrodes_to_actuate, duration_s=duration_s)

        if not electrode_actuators:
            title = 'Warning: failed to actuate all electrodes'
            message = ('No electrode actuators registered to **actuate**: `%s`'
                       % list(electrodes_to_actuate))

            yield asyncio.From(_warning(signals.signal('warning'), message,
                                        title=title, key='no-actuators'))

            # Simulate actuation by waiting for specified duration.
            yield asyncio.From(asyncio.sleep(duration_s))
        else:
            actuation_tasks = zip(*electrode_actuators)[1]

            # Wait for actuations to complete.
            start = dt.datetime.now()
            done, pending = yield asyncio.From(asyncio.wait(actuation_tasks))
            end = dt.datetime.now()

            actuated_electrodes = set()

            exceptions = []

            for d in done:
                try:
                    actuated_electrodes.update(d.result())
                except Exception as exception:
                    # Actuation error occurred.  Save exception and check
                    # remaining responses from actuators.
                    exceptions.append(exception)

            if (electrodes_to_actuate - actuated_electrodes) or exceptions:
                def _error_message():
                    missing_electrodes = (electrodes_to_actuate -
                                        actuated_electrodes)
                    messages = []

                    if missing_electrodes:
                        messages.append('Failed to actuate the following '
                                        'electrodes: %s' %
                                        ', '.join('`%s`' % e
                                                for e in missing_electrodes))
                    if len(exceptions) == 1:
                        messages.append('Actuation error: `%s`' % exceptions[0])
                    elif exceptions:
                        messages.append('Actuation errors:\n%s' % '\n'
                                        .join(' - ' + '`%s`' % e
                                            for e in exceptions))
                    return '\n\n'.join(messages)

                # Send `'warning'` signal to give other plugins an opportunity
                # to handle the warning.
                yield asyncio.From(_warning(signals.signal('warning'),
                                            _error_message(), title='Warning:'
                                            ' actuation error'))
                _L().info('Ignored actuation error(s): `%s`', exceptions)
                # Simulate actuation by waiting for remaining duration.
                remaining_duration = (duration_s - (dt.datetime.now() -
                                                    start).total_seconds())
                if remaining_duration > 0:
                    yield asyncio.From(asyncio.sleep(remaining_duration))
            else:
                # Requested actuations were completed successfully.
                _L().info('actuation completed (actuated electrodes: %s)',
                          actuated_electrodes)

            raise asyncio.Return({'start': start, 'end': end,
                                  'actuated_electrodes':
                                  sorted(actuated_electrodes)})

    @asyncio.coroutine
    def execute_actuations(self, signals, static_states, voltage, frequency,
                           duration_s=0, dynamic=False):
        '''
        .. versionadded:: 2.25


        XXX Coroutine XXX

        Execute *static* and *dynamic* electrode actuations for current
        protocol step.

        See `Issue #253`_ for more details.

        .. _`Issue #253`: https://github.com/sci-bots/microdrop/issues/253#issuecomment-360967363


        Parameters
        ----------
        signals : blinker.Namespace
            Signals namespace.

            .. versionadded:: X.X.X
        static_states : pandas.Series
            Static electrode actuation states, indexed by electrode ID, (e.g.,
            `"electrode001"`).

            .. versionadded:: X.X.X
        voltage : float
            Actuation amplitude as RMS AC voltage (in volts).

            .. versionadded:: X.X.X
        frequency : float
            Actuation frequency (in Hz).

            .. versionadded:: X.X.X
        duration_s : float, optional
            Actuation duration (in seconds).

            .. versionadded:: X.X.X
        dynamic : bool, optional
            If ``True``, query `IElectrodeMutator` plugins for **dynamic**
            actuation states.  Otherwise, only apply local **static** electrode
            actuation states.

        Returns
        -------
        list[dict]
            List of actuation responses, each with fields:

            - ``start``: actuation start timestamp (`datetime.datetime`).
            - ``end``: actuation start timestamp (`datetime.datetime`).
            - ``actuated_electrodes``: actuated electrode IDs (`list`).

        See Also
        --------
        execute_actuation


        .. versionchanged:: 2.25.2
            On steps with dynamic actuations, set duration to zero during final
            loop duration to effectively disable previous dynamic actuations
            before completing the step.

        .. versionchanged:: X.X.X
            Refactor to decouple from ``StepOptionsController`` by using
            :data:`plugin_kwargs` instead of reading parameters using
            :meth:`get_step_options()`.  Add `signals`, `voltage`, `frequency`,
            and `duration_s` parameters.

        .. versionchanged:: X.X.X
            Refactor to request dynamic electrode states through
            :data:`signals` interface instead of using pyutilib
            :func:`emit_signal()`.

        .. versionchanged:: X.X.X
            Add `static_states` parameter.

        .. warning::
            As of X.X.X, any changes to static electrode states will **_not_**
            apply during the execution of a step.  Instead, the changes will
            **only** take effect on _subsequent_ executions of the modified
            step.
        '''
        @asyncio.coroutine
        def _get_dynamic_states():
            # Merge received actuation states from requests with
            # explicit states stored by this plugin.
            requests = []

            responses = signals.signal('get-electrode-states-request').send()

            for receiver_i, co_callback_i in responses:
                request_i = yield asyncio.From(co_callback_i)
                if request_i is not None:
                    requests.append(request_i)
                    logger = _L()
                    if logger.getEffectiveLevel() >= logging.DEBUG:
                            message = ('receiver: %s, actuation_request=%s'
                                        % (receiver_i, request_i))
                            map(logger.debug, message.splitlines())

            if requests:
                combined_states = pd.concat([r[r > 0] for r in requests])
            else:
                combined_states = pd.Series()
            raise asyncio.Return(combined_states)

        actuations = []

        app = get_app()
        # Loop counter
        i = 0
        while True:
            if not dynamic:
                dynamic_electrode_states = pd.Series()
            else:
                # Request dynamic states from `IElectrodeMutator` plugins.
                dynamic_electrode_states =\
                    yield asyncio.From(_get_dynamic_states())

            if any((all([dynamic, i >= 1,
                         dynamic_electrode_states.shape[0] < 1]),
                    app.mode & MODE_REAL_TIME_MASK & ~MODE_RUNNING_MASK)):
                duration_s = 0

            # Execute **static** and **dynamic** electrode states actuation.
            actuation_task = self.execute_actuation(signals, static_states,
                                                    dynamic_electrode_states,
                                                    voltage, frequency,
                                                    duration_s)
            actuated_electrodes = yield asyncio.From(actuation_task)
            actuations.append(actuated_electrodes)

            if dynamic_electrode_states.shape[0] < 1:
                # There are no dynamic electrode actuations, so stop now.
                break
            i += 1

        raise asyncio.Return(actuations)

    @asyncio.coroutine
    def on_step_run(self, plugin_kwargs, signals):
        '''
        .. versionadded:: 2.25

        .. versionchanged:: 2.29
            Convert to coroutine.

        .. versionchanged:: X.X.X
            Refactor to decouple from ``StepOptionsController`` by using
            :data:`plugin_kwargs` instead of reading parameters using
            :meth:`get_step_options()`.  Accept :data:`signals` blinker signals
            namespace parameter.

        .. versionchanged:: X.X.X
            Use default options if plugin parameters not found in
            :data:`plugin_kwargs`.

        Parameters
        ----------
        plugin_kwargs : dict
            Plugin settings as JSON serializable dictionary.
        signals : blinker.Namespace
            Signals namespace.
        '''
        # Wait for plugins to connect to signals as necessary.
        event = asyncio.Event()

        def _on_connected(*args):
            event.set()

        signals.signal('signals-connected').connect(_on_connected, weak=False)
        yield asyncio.From(event.wait())

        app = get_app()
        kwargs = plugin_kwargs.get(self.name, self.get_default_step_options())

        voltage = kwargs['Voltage (V)']
        frequency = kwargs['Frequency (Hz)']
        duration_s = kwargs['Duration (s)']
        static_states = kwargs['electrode_states']
        result = yield asyncio.From(self.execute_actuations(signals,
                                                            static_states,
                                                            voltage, frequency,
                                                            duration_s,
                                                            dynamic=app
                                                            .running))

        logger = _L()  # use logger with function context
        logger.info('%d/%d step actuations completed', len(result),
                    len(result))
        logger.debug('completed actuations: `%s`', result)

    def on_mode_changed(self, old_mode, new_mode):
        '''
        .. versionadded:: 2.25

        .. versionchanged:: X.X.X
            Clear dynamic electrode states when protocol is stopped or
            real-time mode is disabled.
        '''
        if (all([(old_mode & MODE_REAL_TIME_MASK),
                 (new_mode & ~MODE_REAL_TIME_MASK),
                 (new_mode & ~MODE_RUNNING_MASK)]) or
            all([(old_mode & MODE_RUNNING_MASK),
                 (new_mode & ~MODE_RUNNING_MASK)])):
            # Either real-time mode was disabled when it was enabled or
            # protocol just stopped running.
            hub_execute_async(self.name, 'set_dynamic_electrode_states',
                              electrode_states=pd.Series())

    def get_schedule_requests(self, function_name):
        '''
        .. versionadded:: 2.25
            Enable _after_ command plugin and zmq hub to ensure command can be
            registered.
        '''
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.zmq_hub_plugin', self.name),
                    ScheduleRequest('microdrop.command_plugin', self.name)]
        return []

PluginGlobals.pop_env()
