from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import functools as ft
import os
import logging
import shutil
import Queue

from asyncio_helpers import cancellable, sync
from microdrop_utility import FutureVersionError
from microdrop_utility.gui import (yesno, contains_pointer, register_shortcuts,
                                   textentry_validate, text_entry_dialog)
from pygtkhelpers.gthreads import gtk_threadsafe
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import blinker
import gobject
import gtk
import path_helpers as ph
import trollius as asyncio
import zmq

from ..app_context import get_app, get_hub_uri
from logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ScheduleRequest, emit_signal,
                              get_service_instance_by_name, get_service_names)
from ..protocol import Protocol, SerializationError

logger = logging.getLogger(__name__)


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


class ProtocolControllerZmqPlugin(ZmqPlugin):
    '''
    API for controlling protocol state.

     - Start/stop protocol.
     - Load protocol.
     - Go to previous/next/first/last step, or step $i$.
    '''
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        super(ProtocolControllerZmqPlugin, self).__init__(*args, **kwargs)

    def check_sockets(self):
        '''
        .. versionchanged:: 2.15.1
            Shutdown MicroDrop if ``Control-c`` is pressed.
        '''
        try:
            msg_frames = self.command_socket.recv_multipart(zmq.NOBLOCK)
        except zmq.Again:
            pass
        except KeyboardInterrupt:
            # Control-C was pressed.  Shutdown MicroDrop.
            app = get_app()
            app.main_window_controller.shutdown(0)
        else:
            self.on_command_recv(msg_frames)
        return True

    def on_execute__first_step(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.on_first_step()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__last_step(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.on_last_step()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__prev_step(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.on_prev_step()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__next_step(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.on_next_step()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__run_protocol(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.on_run_protocol()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__save_protocol(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.save_protocol()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__delete_step(self, request):
        data = decode_content_data(request)
        try:
            protocol_grid_controller =\
                get_service_instance_by_name('microdrop.gui'
                                             '.protocol_grid_controller',
                                             env='microdrop')
            return protocol_grid_controller.widget.delete_rows()
        except Exception:
            _L().error(str(data), exc_info=True)

    def on_execute__goto_step(self, request):
        data = decode_content_data(request)
        try:
            return self.parent.goto_step(request['step_number'])
        except Exception:
            _L().error(str(data), exc_info=True)


PluginGlobals.push_env('microdrop')


class ProtocolController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.protocol_controller"
        self.executor = ThreadPoolExecutor()
        self.builder = None
        self.label_step_number = None
        self.label_step_number = None
        self.button_first_step = None
        self.button_prev_step = None
        self.button_run_protocol = None
        self.button_next_step = None
        self.button_last_step = None
        self.textentry_protocol_repeats = None
        self._modified = False
        self.plugin = None
        self.plugin_timeout_id = None
        self.step_execution_queue = Queue.Queue()

    ###########################################################################
    # # Properties #
    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        self._modified = value
        self.menu_save_protocol.set_sensitive(value)

    def _register_shortcuts(self):
        app = get_app()
        view = app.main_window_controller.view

        shortcuts = {'<Control>r': self.on_run_protocol,
                     '<Control>s': lambda *args: self.save_protocol(),
                     '<Control>n': lambda *args:
                     app.experiment_log_controller.on_new_experiment(),
                     'A': self.on_first_step,
                     'S': self.on_prev_step,
                     'D': self.on_next_step,
                     'F': self.on_last_step,
                     # `vi`-like bindings.
                     'k': self.on_prev_step,
                     'j': self.on_next_step}

        if app.config.data.get('advanced_ui', False):
            # In `'advanced_ui'` mode, add keyboard shortcut to launch embedded
            # IPython shell.
            import IPython

            shortcuts['<Control>d'] = IPython.embed

        register_shortcuts(view, shortcuts)

    def load_protocol(self, filename):
        '''
        Load protocol from file.

        Parameters
        ----------
        filename : str
            Path to MicroDrop protocol file.
        '''
        filename = ph.path(filename)

        try:
            protocol = Protocol.load(filename)
        except FutureVersionError, why:
            _L().error('''
Could not open protocol: %s

It was created with a newer version of the software.
Protocol is version %s, but only up to version %s is supported with this
version of the software.'''.strip(), filename, why.future_version,
                         why.current_version)
        except Exception, why:
            _L().error("Could not open %s. %s", filename, why)
        else:
            self.activate_protocol(protocol)

    def activate_protocol(self, protocol):
        '''
        Parameters
        ----------
        plugin : microdrop.protocol.Protocol
            MicroDrop protocol.
        '''
        # Check if the protocol contains data from plugins that are not
        # enabled.
        enabled_plugins = (get_service_names(env='microdrop.managed') +
                           get_service_names('microdrop'))
        missing_plugins = []
        for k, v in protocol.plugin_data.items():
            if k not in enabled_plugins and k not in missing_plugins:
                missing_plugins.append(k)
        for i in range(len(protocol)):
            for k, v in protocol[i].plugin_data.items():
                if k not in enabled_plugins and k not in missing_plugins:
                    missing_plugins.append(k)
        self.modified = False
        if missing_plugins:
            logger = _L()  # use logger with method context
            logger.info('protocol missing plugins: %s',
                        ', '.join(missing_plugins))
            result = yesno('Some data in the protocol "%s" requires '
                           'plugins that are not currently installed:'
                           '\n\t%s\nThis data will be ignored unless you '
                           'install and enable these plugins. Would you '
                           'like to permanently clear this data from the '
                           'protocol?' % (protocol.name,
                                          ",\n\t".join(missing_plugins)))
            if result == gtk.RESPONSE_YES:
                logger.info('Deleting protocol data for missing items')
                for k, v in protocol.plugin_data.items():
                    if k in missing_plugins:
                        del protocol.plugin_data[k]
                for i in range(len(protocol)):
                    for k, v in protocol[i].plugin_data.items():
                        if k in missing_plugins:
                            del protocol[i].plugin_data[k]
                self.modified = True
        app = get_app()
        emit_signal("on_protocol_swapped", [app.protocol, protocol])

    def create_protocol(self):
        old_protocol = get_app().protocol
        self.modified = True
        p = Protocol()
        emit_signal("on_protocol_swapped", [old_protocol, p])

    def on_protocol_swapped(self, old_protocol, protocol):
        '''
        .. versionchanged:: 2.25
            Do not execute `run_step()` since it is already triggered by
            swapping to first step in protocol.
        '''
        protocol.plugin_fields = emit_signal('get_step_fields')
        _L().debug('plugin_fields=%s', protocol.plugin_fields)
        protocol.first_step()

    def on_plugin_enable(self):
        app = get_app()
        self.builder = app.builder

        self.label_step_number = self.builder.get_object("label_step_number")
        self.textentry_protocol_repeats = self.builder.get_object(
            "textentry_protocol_repeats")

        for name_i in ('button_first_step', 'button_prev_step',
                       "button_run_protocol", 'button_next_step',
                       'button_last_step', 'menu_protocol',
                       'menu_new_protocol', 'menu_load_protocol',
                       'menu_rename_protocol', 'menu_save_protocol',
                       'menu_save_protocol_as'):
            setattr(self, name_i, app.builder.get_object(name_i))

        app.signals["on_button_first_step_button_release_event"] =\
            self.on_first_step
        app.signals["on_button_prev_step_button_release_event"] =\
            self.on_prev_step
        app.signals["on_button_next_step_button_release_event"] =\
            self.on_next_step
        app.signals["on_button_last_step_button_release_event"] =\
            self.on_last_step
        app.signals["on_button_run_protocol_button_release_event"] =\
            self.on_run_protocol
        app.signals["on_menu_new_protocol_activate"] = self.on_new_protocol
        app.signals["on_menu_load_protocol_activate"] = self.on_load_protocol
        app.signals["on_menu_rename_protocol_activate"] =\
            self.on_rename_protocol
        app.signals["on_menu_save_protocol_activate"] = self.on_save_protocol
        app.signals["on_menu_save_protocol_as_activate"] =\
            self.on_save_protocol_as
        app.signals["on_protocol_import_activate"] = self.on_import_protocol
        app.signals["on_protocol_export_activate"] = self.on_export_protocol
        app.signals["on_textentry_protocol_repeats_focus_out_event"] = \
            self.on_textentry_protocol_repeats_focus_out
        app.signals["on_textentry_protocol_repeats_key_press_event"] = \
            self.on_textentry_protocol_repeats_key_press
        app.protocol_controller = self
        self._register_shortcuts()

        self.menu_protocol.set_sensitive(False)
        self.menu_new_protocol.set_sensitive(False)
        self.menu_load_protocol.set_sensitive(False)
        self.button_first_step.set_sensitive(False)
        self.button_prev_step.set_sensitive(False)
        self.button_run_protocol.set_sensitive(False)
        self.button_next_step.set_sensitive(False)
        self.button_last_step.set_sensitive(False)

        # Initialize sockets.
        self.cleanup_plugin()
        self.plugin = ProtocolControllerZmqPlugin(self, self.name,
                                                  get_hub_uri())
        # Initialize sockets.
        self.plugin.reset()

        # Periodically process outstanding message received on plugin sockets.
        self.plugin_timeout_id = gobject.timeout_add(10, self.plugin
                                                     .check_sockets)

    def cleanup_plugin(self):
        if self.plugin_timeout_id is not None:
            gobject.source_remove(self.plugin_timeout_id)
        if self.plugin is not None:
            self.plugin = None

    def on_plugin_disable(self):
        """
        Handler called once the plugin instance is disabled.
        """
        self.cleanup_plugin()

    def goto_step(self, step_number):
        app = get_app()
        app.protocol.goto_step(step_number)

    def on_first_step(self, widget=None, data=None):
        app = get_app()
        if not app.running and (widget is None or
                                contains_pointer(widget, data.get_coords())):
            app.protocol.first_step()
            return True
        return False

    def on_prev_step(self, widget=None, data=None):
        app = get_app()
        if not app.running and (widget is None or
                                contains_pointer(widget, data.get_coords())):
            app.protocol.prev_step()
            return True
        return False

    def on_next_step(self, widget=None, data=None):
        app = get_app()
        if not app.running and (widget is None or
                                contains_pointer(widget, data.get_coords())):
            app.protocol.next_step()
            return True
        return False

    def on_last_step(self, widget=None, data=None):
        app = get_app()
        if not app.running and (widget is None or
                                contains_pointer(widget, data.get_coords())):
            app.protocol.last_step()
            return True
        return False

    def on_new_protocol(self, widget=None, data=None):
        self.save_check()
        self.create_protocol()

    def on_run_protocol(self, widget=None, data=None):
        if widget is None or contains_pointer(widget, data.get_coords()):
            app = get_app()
            if app.running:
                self.pause_protocol()
            else:
                self.run_protocol()
            return True
        return False

    def on_import_protocol(self, widget=None, data=None):
        app = get_app()
        self.save_check()

        filter_ = gtk.FileFilter()
        filter_.set_name('Exported MicroDrop protocols (*.json)')
        filter_.add_pattern("*.json")

        dialog = gtk.FileChooserDialog(title="Import protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.add_filter(filter_)
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.path.join(app.get_device_directory(),
                                               app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        try:
            if response == gtk.RESPONSE_OK:
                filename = dialog.get_filename()
                self.load_protocol(filename)
                self.modified = True
                emit_signal("on_protocol_changed")
        finally:
            dialog.destroy()

    def on_export_protocol(self, widget=None, data=None):
        app = get_app()

        filter_ = gtk.FileFilter()
        filter_.set_name(' MicroDrop protocols (*.json)')
        filter_.add_pattern("*.json")

        dialog = gtk.FileChooserDialog(title="Export protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_SAVE,
                                                gtk.RESPONSE_OK))
        dialog.add_filter(filter_)
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_name(app.protocol.name)
        dialog.set_current_folder(os.path.join(app.get_device_directory(),
                                               app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        try:
            if response == gtk.RESPONSE_OK:
                filename = ph.path(dialog.get_filename())
                if filename.ext.lower() != '.json':
                    filename = filename + '.json'
                logger = _L()  # use logger with method context
                try:
                    with open(filename, 'w') as output:
                        app.protocol.to_json(output, indent=2)
                except SerializationError, exception:
                    plugin_exception_counts = Counter([e['plugin'] for e in
                                                       exception.exceptions])
                    logger.info('%s: `%s`', exception, exception.exceptions)
                    result = yesno('Error exporting data for the following '
                                   'plugins: `%s`\n\n'
                                   'Would you like to exclude this data and '
                                   'export anyway?' %
                                   ', '.join(sorted(plugin_exception_counts
                                                    .keys())))
                    if result == gtk.RESPONSE_YES:
                        # Delete plugin data that is causing serialization
                        # errors.
                        app.protocol.remove_exceptions(exception.exceptions,
                                                       inplace=True)
                        try:
                            with open(filename, 'w') as output:
                                app.protocol.to_json(output, indent=2)
                        finally:
                            # Mark protocol as changed since some plugin data
                            # was deleted.
                            self.modified = True
                            emit_signal('on_protocol_changed')
                    else:
                        # Abort export.
                        logger.warn('Export cancelled.')
                        return
                logger.info('exported protocol to %s', filename)
        finally:
            dialog.destroy()

    def on_load_protocol(self, widget=None, data=None):
        app = get_app()
        self.save_check()
        dialog = gtk.FileChooserDialog(title="Load protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.path.join(app.get_device_directory(),
                                               app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.load_protocol(filename)
        dialog.destroy()

    def on_rename_protocol(self, widget=None, data=None):
        self.save_protocol(rename=True)

    def on_save_protocol(self, widget=None, data=None):
        self.save_protocol()

    def on_save_protocol_as(self, widget=None, data=None):
        self.save_protocol(save_as=True)

    def on_textentry_protocol_repeats_focus_out(self, widget, data=None):
        self.on_protocol_repeats_changed()

    def on_textentry_protocol_repeats_key_press(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            # user pressed enter
            self.on_protocol_repeats_changed()

    def on_protocol_repeats_changed(self):
        app = get_app()
        if app.protocol:
            app.protocol.n_repeats = \
                textentry_validate(self.textentry_protocol_repeats,
                                   app.protocol.n_repeats, int)

    def save_check(self):
        app = get_app()
        if self.modified:
            result = yesno('Protocol %s has unsaved changes.  Save now?' %
                           app.protocol.name)
            if result == gtk.RESPONSE_YES:
                self.save_protocol()

    def save_protocol(self, save_as=False, rename=False):
        app = get_app()
        name = app.protocol.name
        if app.dmf_device.name:
            if save_as or rename or app.protocol.name is None:
                # if the dialog is cancelled, name = ""
                if name is None:
                    name = ''
                name = text_entry_dialog('Protocol name', name, 'Save protocol')
                if name is None:
                    name = ''

            if name:
                path = os.path.join(app.get_device_directory(),
                                    app.dmf_device.name,
                                    "protocols")
                if not os.path.isdir(path):
                    os.mkdir(path)

                # current file name
                if app.protocol.name:
                    src = os.path.join(path, app.protocol.name)
                dest = os.path.join(path, name)

                # if the protocol name has changed
                if name != app.protocol.name:
                    app.protocol.name = name

                # if we're renaming
                if rename and os.path.isfile(src):
                    shutil.move(src, dest)
                else:  # save the file
                    app.protocol.save(dest)
                self.modified = False
                emit_signal("on_protocol_changed")

    def run_protocol(self):
        '''
        .. versionchanged:: 2.23
            Trigger execution of first step in sequence with :meth:`goto_step`
            instead of calling :meth:`run_step` directly.  This ensures
            consistent behaviour across all steps since all subsequent steps
            are executed by calling :meth:`goto_step`.

        .. versionchanged:: 2.32
            Refactor to manage step execution using the :func:`execute_steps()`
            coroutine.
            .. note:: As of version 2.32, step execution while running a
            protocol is no longer triggered by `on_step_swapped()`.

        See also
        --------
        `run_step()`
        '''
        app = get_app()
        app.running = True
        self.button_run_protocol.set_image(self.builder
                                           .get_object("image_pause"))
        emit_signal("on_protocol_run")
        self.set_sensitivity_of_protocol_navigation_buttons(False)

        signals = blinker.Namespace()
        start_i = app.protocol.current_step_number
        first_pass_complete = []

        @asyncio.coroutine
        def on_step_started(sender, **kwargs):
            _L().debug('%s: `%s`', sender, kwargs)
            step_number = kwargs['i']
            if not first_pass_complete:
                # On first run through protocol, execution starts on currently
                # selected step.
                step_number += start_i
            # Trigger `goto_step()` to update protocol grid selection, etc.
            gtk_threadsafe(app.protocol.goto_step)(step_number)

        @asyncio.coroutine
        def on_step_completed(sender, **kwargs):
            _L().debug('%s: `%s`', sender, kwargs)

        signals.signal('step-started').connect(on_step_started, weak=False)
        signals.signal('step-completed').connect(on_step_completed, weak=False)

        @asyncio.coroutine
        def repeat_steps():
            all_steps = app.protocol.to_dict()['steps']

            for i in xrange(app.protocol.n_repeats):
                steps = all_steps[start_i:] if i == 0 else all_steps
                app.protocol.current_repetition = i
                yield asyncio.From(execute_steps(steps, signals=signals))
                first_pass_complete.append(True)
            gtk_threadsafe(emit_signal)('on_protocol_finished')

        task = cancellable(repeat_steps)
        future = self.executor.submit(task)
        self.step_execution_queue.put((task, future))

        def on_done(future):
            try:
                future.result()
            except asyncio.CancelledError:
                # Protocol was paused/cancelled.
                pass
            except Exception as exception:
                _L().info('`%s`', exception, exc_info=True)
                gtk_threadsafe(_L().error)('`%s`', exception)
            finally:
                gtk_threadsafe(self.pause_protocol)()

        future.add_done_callback(on_done)

    def pause_protocol(self):
        '''
        .. versionchanged:: 2.30
            Cancel any currently executing steps.
        '''
        self.cancel_steps()
        app = get_app()
        app.running = False
        self.button_run_protocol.set_image(self.builder
                                           .get_object("image_play"))
        emit_signal("on_protocol_pause")
        self.set_sensitivity_of_protocol_navigation_buttons(True)

    def set_sensitivity_of_protocol_navigation_buttons(self, sensitive):
        self.button_first_step.set_sensitive(sensitive)
        self.button_prev_step.set_sensitive(sensitive)
        self.button_next_step.set_sensitive(sensitive)
        self.button_last_step.set_sensitive(sensitive)

    def cancel_steps(self):
        '''
        .. versionadded:: 2.30

        Cancel any current step executions.
        '''
        while True:
            try:
                step_task, future = self.step_execution_queue.get_nowait()
                if not future.done():
                    _L().info('Cancel running step.')
                    try:
                        step_task.cancel()
                    except RuntimeError:
                        pass
            except Queue.Empty:
                break

    def run_step(self):
        '''
        Execute currently selected step.

        .. versionchanged:: 2.25
            Only wait for other plugins if protocol is running.

        .. versionchanged:: 2.29
            Refactor to run `on_step_run()` calls as `asyncio.coroutine`
            functions.

        .. versionchanged:: 2.29.1
            Pause protocol if any plugin encountered an exception during
            ``on_step_run`` and display an error message.

        .. versionchanged:: 2.30
            Fix protocol repeats.

        .. versionchanged:: 2.30
            Refactor pass plugin step options as :data:`plugin_kwargs` argument
            to ``on_step_run()`` signal instead of each plugin reading
            parameters using :meth:`get_step_options()`.to decouple from
            ``StepOptionsController``.  Send :data:`signals` parameter to
            ``on_step_run()`` signal as well, as a signals namespace for
            plugins during step execution.

            .. warning::
                Plugins **MUST**::
                - connect blinker :data:`signals` callbacks before any
                  yielding call (e.g., ``yield asyncio.From(...)``) in the
                  ``on_step_run()`` coroutine; **_and_**
                - wait for the ``'signals-connected'`` blinker signal to be
                  sent before sending any signal to ensure all other plugins
                  have had a chance to connect any relevant callbacks.

        .. versionchanged:: 2.32
            Refactor to manage single step execution using the
            :func:`execute_step()` coroutine.
            .. note:: As of version 2.32, this method is _only _ used for
            execute of a _single step_ (without executing the whole protocol).

        See also
        --------
        `run_protocol()`
        '''
        app = get_app()
        if app.protocol and app.dmf_device:
            self.cancel_steps()
            task = cancellable(execute_step)
            # Take snapshot of arguments for current step.
            plugin_kwargs = copy.deepcopy(app.protocol.current_step()
                                          .plugin_data)
            future = self.executor.submit(task, plugin_kwargs)
            self.step_execution_queue.put((task, future))

    def _get_dmf_control_fields(self, step_number):
        step = get_app().protocol.get_step(step_number)
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        service = get_service_instance_by_name(dmf_plugin_name)
        if service:
            return service.get_step_values(step_number)
        return None

    def on_step_options_changed(self, plugin, step_number):
        '''
        Mark protocol as modified when step options have changed for a plugin.

        .. versionchanged:: 2.25
            Emit `on_step_swapped` instead of calling `run_step()`.  Only emit
            `on_step_swapped` if protocol is not running to avoid trying to run
            the step when it is already running.
        '''
        self.modified = True
        emit_signal('on_protocol_changed')
        app = get_app()
        if not app.running:
            step_number = app.protocol.current_step_number
            emit_signal('on_step_swapped', [step_number, step_number])

    def on_step_created(self, step_number):
        '''
        Mark protocol as modified when a new step is created.
        '''
        self.modified = True
        emit_signal('on_protocol_changed')

    def on_step_swapped(self, original_step_number, step_number):
        '''
        .. versionchanged:: 2.32
            Only call :meth:`run_step()` if in real-time mode while protocol is
            not running.  Otherwise, step execution is handled completely by
            :meth:`run_protocol()`.
        '''
        _L().debug('%s -> %s', original_step_number, step_number)
        self._update_labels()
        app = get_app()
        if app.realtime_mode and not app.running:
            self.run_step()

    def _update_labels(self):
        app = get_app()
        self.label_step_number.set_text("Step: %d/%d\tRepetition: %d/%d" %
                                        (app.protocol.current_step_number + 1,
                                         len(app.protocol.steps),
                                         app.protocol.current_repetition + 1,
                                         app.protocol.n_repeats))
        self.textentry_protocol_repeats.set_text(str(app.protocol.n_repeats))

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        if dmf_device:
            self.menu_protocol.set_sensitive(True)
            self.menu_new_protocol.set_sensitive(True)
            self.menu_load_protocol.set_sensitive(True)
            self.button_first_step.set_sensitive(True)
            self.button_prev_step.set_sensitive(True)
            self.button_run_protocol.set_sensitive(True)
            self.button_next_step.set_sensitive(True)
            self.button_last_step.set_sensitive(True)
            self.create_protocol()

    def on_app_exit(self):
        self.cleanup_plugin()
        app = get_app()
        if self.modified:
            result = yesno('Protocol %s has unsaved changes.  Save now?' %
                           app.protocol.name)
            if result == gtk.RESPONSE_YES:
                self.save_protocol()

    def on_experiment_log_changed(self, experiment_log):
        # go to the first step when a new experiment starts
        protocol = get_app().protocol
        if protocol:
            protocol.first_step()

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        elif function_name == 'on_dmf_device_swapped':
            # make sure that the app gets a reference to the device before we
            # create a new protocol
            return [ScheduleRequest('microdrop.app', self.name)]
        elif function_name == 'on_protocol_swapped':
            # make sure that the app gets a reference to the protocol before we
            # process the on_protocol_swapped signal
            return [ScheduleRequest('microdrop.app', self.name)]
        return []


PluginGlobals.pop_env()
