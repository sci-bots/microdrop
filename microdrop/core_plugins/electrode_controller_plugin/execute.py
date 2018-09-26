'''
.. versionadded:: 2.30
'''
import datetime as dt
import logging

from logging_helpers import _L
import pandas as pd
import si_prefix as si
import trollius as asyncio

NAME = 'microdrop.electrode_controller_plugin'


@asyncio.coroutine
def _warning(signal, message, **kwargs):
    '''
    XXX Coroutine XXX

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


@asyncio.coroutine
def execute_actuation(signals, static_states, dynamic_states,
                        voltage, frequency, duration_s):
    '''
    XXX Coroutine XXX

    Execute specified *static* and *dynamic* electrode actuations.

    Parameters
    ----------
    signals : blinker.Namespace
        Signals namespace.
    static_states : pandas.Series
        Static electrode actuation states, indexed by electrode ID, (e.g.,
        `"electrode001"`).
    dynamic_states : pandas.Series
        Dynamic electrode actuation states, indexed by electrode ID.
    voltage : float
        Actuation amplitude as RMS AC voltage (in volts).
    frequency : float
        Actuation frequency (in Hz).
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

    .. versionchanged:: 2.30
        Add `signals`, `voltage` and `frequency` parameters.  Refactor the
        to set waveform parameters using ``signals`` namespace instead.

    .. versionchanged:: 2.30
        Refactor electrode actuation requests to use :data:`signals`
        interface instead of using pyutilib :func:`emit_signal()`.

    .. versionchanged:: 2.31.1
        Prevent error dialog prompt if coroutine is cancelled while calling
        ``set_waveform()`` callbacks.
    '''
    # Notify other plugins that dynamic electrodes states have changed.
    responses = (signals.signal('dynamic-electrode-states-changed')
                 .send(NAME, electrode_states=dynamic_states))
    yield asyncio.From(asyncio.gather(*(r[1] for r in responses)))

    static_electrodes_to_actuate = set(static_states[static_states > 0].index)
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
            except asyncio.CancelledError:
                raise
            except Exception as exception:
                pass
            else:
                if receivers:
                    raise asyncio.Return(zip(receivers, results))

        if exception is not None:
            message = ('Error setting **%s**: `%s`' % (key, exception))
        else:
            message = ('No waveform generators available to set **%s**.' % key)

        yield asyncio.From(_warning(signals.signal('warning'), message,
                                    title='Warning: failed to set %s' % key,
                                    key='waveform-%s' % key))

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
        message = ('No electrode actuators registered to **actuate**: `%s`' %
                   list(electrodes_to_actuate))

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
                    messages.append('**Actuation error:** `%s`' %
                                    exceptions[0])
                elif exceptions:
                    messages.append('**Actuation errors:**\n%s' % '\n'
                                    .join(' - ' + '`%s`' % e
                                          for e in exceptions))
                return '\n\n'.join(messages)

            # Send `'warning'` signal to give other plugins an opportunity
            # to handle the warning.
            yield asyncio.From(_warning(signals.signal('warning'),
                                        _error_message(), title='Warning:'
                                        ' actuation error',
                                        key='actuation-error'))
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
def execute_actuations(signals, static_states, voltage, frequency,
                       duration_s=0, dynamic=False):
    '''
    XXX Coroutine XXX

    Execute *static* and *dynamic* electrode actuations for current
    protocol step.

    See `Issue #253`_ for more details.

    .. _`Issue #253`: https://github.com/sci-bots/microdrop/issues/253#issuecomment-360967363


    Parameters
    ----------
    signals : blinker.Namespace
        Signals namespace.
    static_states : pandas.Series
        Static electrode actuation states, indexed by electrode ID, (e.g.,
        `"electrode001"`).
    voltage : float
        Actuation amplitude as RMS AC voltage (in volts).
    frequency : float
        Actuation frequency (in Hz).
    duration_s : float, optional
        Actuation duration (in seconds).
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

    .. versionchanged:: 2.30
        Refactor to decouple from ``StepOptionsController`` by using
        :data:`plugin_kwargs` instead of reading parameters using
        :meth:`get_step_options()`.  Add `signals`, `voltage`, `frequency`,
        and `duration_s` parameters.

    .. versionchanged:: 2.30
        Refactor to request dynamic electrode states through
        :data:`signals` interface instead of using pyutilib
        :func:`emit_signal()`.

    .. versionchanged:: 2.30
        Add `static_states` parameter.

    .. warning::
        As of 2.30, any changes to static electrode states will **_not_**
        apply during the execution of a step.  Instead, the changes will
        **only** take effect on _subsequent_ executions of the modified
        step.
    '''
    @asyncio.coroutine
    def _dynamic_states():
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
                        message = ('receiver: %s, actuation_request=%s' %
                                   (receiver_i, request_i))
                        map(logger.debug, message.splitlines())

        if requests:
            combined_states = pd.concat([r[r > 0] for r in requests])
        else:
            combined_states = pd.Series()
        raise asyncio.Return(combined_states)

    actuations = []

    # Loop counter
    i = 0
    while True:
        if not dynamic:
            dynamic_electrode_states = pd.Series()
        else:
            # Request dynamic states from `IElectrodeMutator` plugins.
            dynamic_electrode_states = yield asyncio.From(_dynamic_states())

        if all([dynamic, i >= 1, dynamic_electrode_states.shape[0] < 1]):
            duration_s = 0

        # Execute **static** and **dynamic** electrode states actuation.
        actuation_task = execute_actuation(signals, static_states,
                                           dynamic_electrode_states, voltage,
                                           frequency, duration_s)
        actuated_electrodes = yield asyncio.From(actuation_task)
        actuations.append(actuated_electrodes)

        if dynamic_electrode_states.shape[0] < 1:
            # There are no dynamic electrode actuations, so stop now.
            break
        i += 1

    raise asyncio.Return(actuations)


@asyncio.coroutine
def execute(plugin_kwargs, signals):
    '''
    XXX Coroutine XXX

    Parameters
    ----------
    plugin_kwargs : dict
        Plugin settings as JSON serializable dictionary.
    signals : blinker.Namespace
        Signals namespace.
    '''
    if NAME not in plugin_kwargs:
        raise asyncio.Return([])
    else:
        kwargs = plugin_kwargs[NAME]

    # Wait for plugins to connect to signals as necessary.
    event = asyncio.Event()
    signals.signal('signals-connected').connect(lambda *args: event.set(),
                                                weak=False)
    yield asyncio.From(event.wait())

    voltage = kwargs['Voltage (V)']
    frequency = kwargs['Frequency (Hz)']
    duration_s = kwargs['Duration (s)']
    static_states = kwargs.get('electrode_states', pd.Series())
    dynamic = kwargs.get('dynamic', True)
    result = yield asyncio.From(execute_actuations(signals, static_states,
                                                   voltage, frequency,
                                                   duration_s,
                                                   dynamic=dynamic))

    logger = _L()  # use logger with function context
    logger.info('%d/%d actuations completed', len(result), len(result))
    logger.debug('completed actuations: `%s`', result)
    raise asyncio.Return(result)
