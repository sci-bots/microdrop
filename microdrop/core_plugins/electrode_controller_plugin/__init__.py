from __future__ import division, print_function, unicode_literals
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import functools as ft
import itertools as it
import logging
import pprint
import threading
import uuid

from asyncio_helpers import cancellable, sync
from flatland import Float, Form
from flatland.validation import ValueAtLeast
from logging_helpers import _L, caller_name
from pygtkhelpers.gthreads import gtk_threadsafe
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import gtk
import pandas as pd
import si_prefix as si
import trollius as asyncio
import zmq

from ...app_context import (get_app, get_hub_uri, MODE_RUNNING_MASK,
                            MODE_REAL_TIME_MASK)
from ...interfaces import (IApplicationMode, IElectrodeActuator,
                           IElectrodeController, IElectrodeMutator,
                           IWaveformGenerator)
from ...plugin_helpers import (StepOptionsController, AppDataController,
                               hub_execute, hub_execute_async)
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements, emit_signal, ScheduleRequest)

logger = logging.getLogger(__name__)


def ignorable_warning(**kwargs):
    '''
    Display warning dialog with checkbox to ignore further warnings.

    Returns
    -------
    dict
        Response with fields:

        - ``ignore``: ignore warning (`bool`).
        - ``always``: treat all similar warnings the same way (`bool`).


    .. versionadded:: 2.25
    '''
    dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_YES_NO,
                               type=gtk.MESSAGE_WARNING)

    for k, v in kwargs.items():
        setattr(dialog.props, k, v)

    content_area = dialog.get_content_area()
    vbox = content_area.get_children()[0].get_children()[-1]
    check_button = gtk.CheckButton(label='Let me _decide for each warning',
                                   use_underline=True)
    vbox.pack_end(check_button)
    check_button.show()

    dialog.set_default_response(gtk.RESPONSE_YES)

    dialog.props.secondary_use_markup = True
    dialog.props.secondary_text = ('<b>Would you like to ignore and '
                                   'continue?</b>')
    try:
        response = dialog.run()
        return {'ignore': (response == gtk.RESPONSE_YES),
                'always': not check_button.props.active}
    finally:
        dialog.destroy()


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
        '''
        # Set the state of DMF device channels.
        step_options = self.parent.get_step_options()
        step_options['electrode_states'] = electrode_states[electrode_states >
                                                            0]
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
        data = decode_content_data(request)
        try:
            return self.set_electrode_states(data['electrode_states'],
                                             save=data.get('save', True))
        except Exception:
            gtk_threadsafe(ft.partial(logger.error, str(data),
                                      exc_info=True))()

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
    implements(IElectrodeController)
    implements(IApplicationMode)
    plugin_name = 'microdrop.electrode_controller_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.stopped = threading.Event()
        self._active_actuation = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.warnings_ignoring = dict()

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
        """
        app_values = self.get_app_values()
        if not app_values:
            app_values = self.get_default_app_options()
            self.set_app_values(app_values)
        return Form.of(Float.named('Duration (s)')
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
    def execute_actuation(self, static_states, dynamic_states, duration_s):
        '''
        .. versionadded:: 2.25


        XXX Coroutine XXX

        Execute specified *static* and *dynamic* electrode actuations.

        Parameters
        ----------
        static_states : pandas.Series
            Static electrode actuation states, indexed by electrode ID, (e.g.,
            `"electrode001"`).
        dynamic_states : pandas.Series
            Dynamic electrode actuation states, indexed by electrode ID.
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
        '''
        # Notify other ZMQ plugins that `dynamic_electrodes_states` have
        # changed.
        @sync(gtk_threadsafe)
        def notify_dynamic_states(dynamic_electrode_states):
            try:
                return hub_execute(self.name, 'set_dynamic_electrode_states',
                                   electrode_states=dynamic_electrode_states)
            except Exception as exception:
                _L().warning(str(exception), exc_info=True)
                return None

        response = yield asyncio.From(notify_dynamic_states(dynamic_states))

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

        step_options = self.get_step_options()
        voltage = step_options['Voltage (V)']
        frequency = step_options['Frequency (Hz)']

        def set_waveform(key, value):
            try:
                result = emit_signal("set_%s" % key, value,
                                     interface=IWaveformGenerator)
                if result:
                    return result
            except Exception as exception:
                result = exception

            if not key in self.warnings_ignoring:
                response = ignorable_warning(title='Warning: failed to  set '
                                             '%s' % key, text='No waveform '
                                             'generators available to set '
                                             '<b>%s</b>.' % key,
                                             use_markup=True)
                if response['always']:
                    self.warnings_ignoring[key] = response['ignore']
                ignore = response['ignore']
            else:
                ignore = self.warnings_ignoring[key]

            if not ignore:
                return RuntimeError('No waveform generators available to set '
                                    '%s to %s' % (key, value))

        for key, value, unit in (('frequency', frequency, 'Hz'),
                                 ('voltage', voltage, 'V')):
            # Apply waveform in main (i.e., Gtk) thread.
            waveform_result = \
                yield asyncio.From(sync(gtk_threadsafe)
                                   (ft.partial(set_waveform, key, value))())

            if isinstance(waveform_result, Exception):
                raise waveform_result
            elif waveform_result:
                _L().info('%s set to %s%s (plugins: `%s`)', key,
                          si.si_format(value), unit, waveform_result.keys())

        electrode_actuators = emit_signal('on_actuation_request',
                                          args=[s_electrodes_to_actuate,
                                                duration_s],
                                          interface=IElectrodeActuator)

        if not electrode_actuators:
            if not 'actuate' in self.warnings_ignoring:
                @sync(gtk_threadsafe)
                def _warning():
                    return ignorable_warning(title='Warning: failed to '
                                             'actuate all electrodes',
                                             text='No electrode actuators '
                                             'registered to '
                                             '<b>actuate</b>: <tt>%s</tt>'
                                             % list(electrodes_to_actuate),
                                             use_markup=True)

                response = yield asyncio.From(_warning())
                if response['always']:
                    self.warnings_ignoring['actuate'] = response['ignore']
                ignore = response['ignore']
            else:
                ignore = self.warnings_ignoring['actuate']

            if not ignore:
                raise RuntimeError('No electrode actuators registered to '
                                   'actuate: `%s`' %
                                   list(electrodes_to_actuate))
            else:
                # Simulate actuation by waiting for specified duration.
                yield asyncio.From(asyncio.sleep(duration_s))
        else:
            actuation_tasks = electrode_actuators.values()

            # Wait for actuations to complete.
            start = dt.datetime.now()
            done, pending = yield asyncio.From(asyncio.wait(actuation_tasks))
            end = dt.datetime.now()
            actuated_electrodes = set(it.chain(*(d.result() for d in done)))

            if electrodes_to_actuate - actuated_electrodes:
                task = sync(gtk_threadsafe)\
                    (_L().error)('failed to actuate the following '
                                 'electrodes: %s', electrodes_to_actuate -
                                 actuated_electrodes)
                yield asyncio.From(task)
            else:
                # Requested actuations were completed successfully.
                _L().info('actuation completed (actuated electrodes: %s)',
                          actuated_electrodes)

            raise asyncio.Return({'start': start, 'end': end,
                                  'actuated_electrodes':
                                  sorted(actuated_electrodes)})

    @asyncio.coroutine
    def execute_actuations(self, dynamic=False):
        '''
        .. versionadded:: 2.25


        XXX Coroutine XXX

        Execute *static* and *dynamic* electrode actuations for current
        protocol step.

        See `Issue #253`_ for more details.

        .. _`Issue #253`: https://github.com/sci-bots/microdrop/issues/253#issuecomment-360967363


        Parameters
        ----------
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
        '''
        def _get_dynamic_states():
            # Merge received actuation states from requests with
            # explicit states stored by this plugin.
            responses = emit_signal('get_electrode_states_request',
                                    interface=IElectrodeMutator)
            actuation_requests = {k: v for k, v in responses.items()
                                if v is not None}

            if actuation_requests:
                logger = _L()
                if logger.getEffectiveLevel() >= logging.DEBUG:
                    for plugin_name_i, actuation_request_i in \
                            actuation_requests.iteritems():
                        message = ('plugin: %s, actuation_request=%s' %
                                   (plugin_name_i, actuation_request_i))
                        map(logger.debug, message.splitlines())

                return pd.concat([actuation_request_i[actuation_request_i > 0]
                                  for actuation_request_i in
                                  actuation_requests.itervalues()])
            else:
                return pd.Series()

        actuations = []

        app = get_app()
        # Loop counter
        i = 0
        while True:
            # Start with electrodes specified by this plugin.
            step_states = self.plugin.electrode_states.copy()

            if not dynamic:
                dynamic_electrode_states = pd.Series()
            else:
                # Request dynamic states from `IElectrodeMutator` plugins.
                dynamic_electrode_states = _get_dynamic_states()

            if any((all([dynamic, i >= 1,
                         dynamic_electrode_states.shape[0] < 1]),
                    app.mode & MODE_REAL_TIME_MASK & ~MODE_RUNNING_MASK)):
                duration_s = 0
            else:
                step_options = self.get_step_options()
                duration_s = step_options.get('Duration (s)', 0)

            # Execute **static** and **dynamic** electrode states actuation.
            actuation_task = self.execute_actuation(step_states,
                                                    dynamic_electrode_states,
                                                    duration_s)
            actuated_electrodes = yield asyncio.From(actuation_task)
            actuations.append(actuated_electrodes)

            if dynamic_electrode_states.shape[0] < 1:
                # There are no dynamic electrode actuations, so stop now.
                break
            i += 1

        raise asyncio.Return(actuations)

    def on_step_run(self):
        '''
        .. versionadded:: 2.25
        '''
        app = get_app()
        # Wrap coroutine to provide `cancel()` method.
        self._active_actuation = cancellable(self.execute_actuations)
        # Run asyncio loop in background thread.
        self._active_actuation.future = \
            self.executor.submit(self._active_actuation, app.running)
        future = self._active_actuation.future
        future.uuid1 = uuid.uuid1()
        _L().info('apply step actuations (%s)', future.uuid1)

        # Wait for coroutine to finish.
        @gtk_threadsafe
        def on_finished(future):
            try:
                result = future.result()
                if app.running:
                    emit_signal('on_step_complete', [self.name, None])
                logger = _L()  # use logger with function context
                logger.info('%d/%d step actuations completed (%s)',
                            len(result), len(result), future.uuid1)
                logger.debug('completed actuations: `%s`', result)
            except asyncio.CancelledError:
                _L().info('Step was cancelled (%s).', future.uuid1)
            except Exception as exception:
                _L().error('Error executing step actuations: %s', exception,
                           exc_info=True)
                if app.running:
                    emit_signal('on_step_complete', [self.name, 'Fail'])
            finally:
                self._active_actuation = None

        future.add_done_callback(on_finished)

    def cancel_actuation(self):
        '''
        .. versionadded:: 2.25
        '''
        if self._active_actuation is not None and\
                (not hasattr(self._active_actuation, 'future') or
                 not self._active_actuation.future.done()):
            _L().debug('Cancel previous actuation.')
            self._active_actuation.started.wait()
            # Cancel all asyncio tasks.
            self._active_actuation.cancel()
            self._active_actuation = None

        # Disable dynamic states.
        def _disable_dynamic(result):
            app = get_app()
            self._active_actuation = cancellable(self.execute_actuation)
            static_states = (self.plugin.electrode_states.copy()
                             if app.realtime_mode else pd.Series())
            self.executor.submit(self._active_actuation, static_states,
                                 pd.Series(), duration_s=0)

        if hasattr(self._active_actuation, 'future'):
            self._active_actuation.future.add_done_callback(_disable_dynamic)
        else:
            _disable_dynamic(None)

    def on_step_complete(self, plugin_name, return_value):
        '''
        .. versionchanged:: 2.25
            Cancel actuation coroutine if step did not complete as expected.
        '''
        if return_value is not None:
            # Step did not complete as expected.  Cancel actuation.
            self.cancel_actuation()

    def on_protocol_pause(self):
        '''
        Handler called when a protocol is paused.


        .. versionchanged:: 2.25
        '''
        # Protocol was paused.  Stop executing current step.
        self.cancel_actuation()

    def on_mode_changed(self, old_mode, new_mode):
        '''
        .. versionadded:: 2.25
        '''
        _L().info('Mode changed: `%s` -> `%s`', old_mode, new_mode)
        if (all([(old_mode & ~MODE_REAL_TIME_MASK),
                 (new_mode & MODE_REAL_TIME_MASK),
                 (new_mode & ~MODE_RUNNING_MASK)]) or
            all([(old_mode & ~MODE_RUNNING_MASK),
                 (new_mode & MODE_RUNNING_MASK)])):
            # Either real-time mode was enabled when it wasn't before or
            # protocol just started running.
            # Reset to not ignoring any warnings.
            self.warnings_ignoring.clear()

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
