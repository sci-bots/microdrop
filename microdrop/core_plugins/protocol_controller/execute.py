'''
.. versionadded:: 2.35.0
'''
import copy

from logging_helpers import _L
import blinker
import trollius as asyncio

from ...plugin_manager import emit_signal


@asyncio.coroutine
def execute_step(plugin_kwargs):
    '''
    .. versionadded:: 2.32

    XXX Coroutine XXX

    Execute a single protocol step.

    Parameters
    ----------
    plugin_kwargs : dict
        Plugin keyword arguments, indexed by plugin name.

    Returns
    -------
    list
        Return values from plugin ``on_step_run()`` coroutines.
    '''
    # Take snapshot of arguments for current step.
    plugin_kwargs = copy.deepcopy(plugin_kwargs)

    signals = blinker.Namespace()

    @asyncio.coroutine
    def notify_signals_connected():
        yield asyncio.From(asyncio.sleep(0))
        signals.signal('signals-connected').send(None)

    loop = asyncio.get_event_loop()
    # Get list of coroutine futures by emitting `on_step_run()`.
    plugin_step_tasks = emit_signal("on_step_run", args=[plugin_kwargs,
                                                         signals])
    future = asyncio.wait(plugin_step_tasks.values())

    loop.create_task(notify_signals_connected())
    result = yield asyncio.From(future)
    raise asyncio.Return(result)


@asyncio.coroutine
def execute_steps(steps, signals=None):
    '''
    .. versionadded:: 2.32

    Parameters
    ----------
    steps : list[dict]
        List of plugin keyword argument dictionaries.
    signals : blinker.Namespace, optional
        Signals namespace where signals are sent through.

    Signals
    -------
    step-started
        Parameters::
        - ``i``: step index
        - ``plugin_kwargs``: plugin keyword arguments
        - ``steps_count``: total number of steps
    step-completed
        Parameters::
        - ``i``: step index
        - ``plugin_kwargs``: plugin keyword arguments
        - ``steps_count``: total number of steps
        - ``result``: list of plugin step return values
    '''
    if signals is None:
        signals = blinker.Namespace()

    for i, step_i in enumerate(steps):
        # Send notification that step has completed.
        responses = signals.signal('step-started')\
            .send('execute_steps', i=i, plugin_kwargs=step_i,
                  steps_count=len(steps))
        yield asyncio.From(asyncio.gather(*(r[1] for r in responses)))
        # XXX Execute `on_step_run` coroutines in background thread
        # event-loop.
        try:
            done, pending = yield asyncio.From(execute_step(step_i))

            exceptions = []

            for d in done:
                try:
                    d.result()
                except Exception as exception:
                    exceptions.append(exception)
                    _L().debug('Error: %s', exception, exc_info=True)

            if exceptions:
                use_markup = False
                monospace_format = '<tt>%s</tt>' if use_markup else '%s'

                if len(exceptions) == 1:
                    message = (' ' + monospace_format % exceptions[0])
                elif exceptions:
                    message = ('\n%s' % '\n'.join(' - ' + monospace_format
                                                    % e for e in exceptions))
                raise RuntimeError('Error executing step:%s' % message)
        except asyncio.CancelledError:
            _L().debug('Cancelling protocol.', exc_info=True)
            raise
        except Exception as exception:
            _L().debug('Error executing step: `%s`', exception, exc_info=True)
            raise
        else:
            # All plugins have completed the step.
            # Send notification that step has completed.
            responses = signals.signal('step-completed')\
                .send('execute_steps', i=i, plugin_kwargs=step_i,
                      result=[r.result() for r in done],
                      steps_count=len(steps))
            yield asyncio.From(asyncio.gather(*(r[1] for r in responses)))
