from contextlib import closing
from datetime import datetime
import logging
import os
import pdb
import threading
import webbrowser

from debounce import Debounce
from pygtkhelpers.gthreads import gtk_threadsafe
from pygtkhelpers.proxy import proxy_for
from microdrop_utility import wrap_string
from microdrop_utility.gui import DEFAULTS
import gobject
import gtk
import pkgutil
import trollius as asyncio
try:
    import pudb
    PUDB_AVAILABLE = True
except ImportError:
    PUDB_AVAILABLE = False

from ..interfaces import IApplicationMode
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ScheduleRequest, ILoggingPlugin,
                              emit_signal, get_service_instance_by_name)
from ..app_context import get_app, MODE_RUNNING_MASK
from logging_helpers import _L  #: .. versionadded:: 2.20
from .. import __version__

logger = logging.getLogger(__name__)

PluginGlobals.push_env('microdrop')


class MainWindowController(SingletonPlugin):
    implements(IPlugin)
    implements(ILoggingPlugin)
    implements(IApplicationMode)

    def __init__(self):
        '''
        .. versionchanged:: 2.21
            Read glade file using ``pkgutil`` to also support loading from
            ``.zip`` files (e.g., in app packaged with Py2Exe).

        .. versionchanged:: 2.31
            Remove control board status label; pack status labels in
            :class:`gtk.HBox` to allow other plugins to pack widgets
            horizontally adjacent.
        '''
        self._shutting_down = threading.Event()
        self.name = "microdrop.gui.main_window_controller"
        self.builder = None
        self.view = None
        self.label_experiment_id = None
        self.label_device_name = None
        self.label_protocol_name = None
        self.checkbutton_realtime_mode = None
        self.menu_tools = None
        self.menu_view = None
        self.step_start_time = None
        self.step_timeout_id = None
        gtk.link_button_set_uri_hook(self.on_url_clicked)

        builder = gtk.Builder()
        # Read glade file using `pkgutil` to also support loading from `.zip`
        # files (e.g., in app packaged with Py2Exe).
        glade_str = pkgutil.get_data(__name__,
                                     'glade/text_input_dialog.glade')
        builder.add_from_string(glade_str)

        self.text_input_dialog = builder.get_object("window")
        self.text_input_dialog.textentry = builder.get_object("textentry")
        self.text_input_dialog.label = builder.get_object("label")

    def enable_keyboard_shortcuts(self):
        for group_i in self.accel_groups:
            self.view.add_accel_group(group_i)

    def disable_keyboard_shortcuts(self):
        for group_i in self.accel_groups:
            self.view.remove_accel_group(group_i, cached=True)

    def on_plugin_enable(self):
        '''
        .. versionchanged:: 2.16
            Save window layout whenever window is resized or moved.

        .. versionchanged:: 2.21
            Read glade file using ``pkgutil`` to also support loading from
            ``.zip`` files (e.g., in app packaged with Py2Exe).

        .. versionchanged:: 2.29.1
            Add mnemonic accelerators to ``De_bug`` and ``_IPython`` advance UI
            menu items.
        '''
        app = get_app()
        # Read glade file using `pkgutil` to also support loading from `.zip`
        # files (e.g., in app packaged with Py2Exe).
        glade_str = pkgutil.get_data(__name__, 'glade/main_window.glade')
        app.builder.add_from_string(glade_str)

        self.view = app.builder.get_object("window")

        self.view._add_accel_group = self.view.add_accel_group

        def add_accel_group(accel_group):
            self.view._add_accel_group(accel_group)
            if not hasattr(self, 'accel_groups'):
                self.accel_groups = set()
            self.accel_groups.add(accel_group)
        self.view.add_accel_group = add_accel_group

        self.view._remove_accel_group = self.view.remove_accel_group

        def remove_accel_group(accel_group, cached=True):
            self.view._remove_accel_group(accel_group)
            if not cached and hasattr(self, 'accel_groups'):
                self.accel_groups.remove(accel_group)
        self.view.remove_accel_group = remove_accel_group

        self.vbox2 = app.builder.get_object('vbox2')
        # [Load icon from string][1] to support loading from `.zip` file.
        #
        # [1]: https://bytes.com/topic/python/answers/29401-pygtk-creating-pixbuf-image-data#post109157
        icon_str = pkgutil.get_data('microdrop', 'microdrop.ico')
        with closing(gtk.gdk.PixbufLoader('ico')) as loader:
            loader.write(icon_str)
        icon_pixbuf = loader.get_pixbuf()
        self.view.set_icon(icon_pixbuf)
        DEFAULTS.parent_widget = self.view

        for widget_name in ('box_step', 'checkbutton_realtime_mode',
                            'label_device_name', 'label_experiment_id',
                            'label_protocol_name', 'label_protocol_name',
                            'label_step_time', 'menu_tools', 'menu_view',
                            'button_open_log_directory',
                            'button_open_log_notes'):
            setattr(self, widget_name, app.builder.get_object(widget_name))

        app.signals["on_menu_quit_activate"] = self.on_destroy
        app.signals["on_menu_about_activate"] = self.on_about
        app.signals["on_menu_online_help_activate"] = \
            self.on_menu_online_help_activate

        debounced_save_layout = Debounce(self._save_layout, wait=500)

        _L().info('Resize mode: %s', self.view.get_resize_mode())
        app.signals["on_window_check_resize"] = \
            lambda *args: debounced_save_layout()

        app.signals["on_window_destroy"] = self.on_destroy
        app.signals["on_window_delete_event"] = self.on_delete_event
        app.signals["on_checkbutton_realtime_mode_toggled"] = \
            self.on_realtime_mode_toggled
        app.signals["on_button_open_log_directory_clicked"] = \
            self.on_button_open_log_directory
        app.signals["on_button_open_log_notes_clicked"] = \
            self.on_button_open_log_notes
        app.signals["on_menu_app_options_activate"] = \
            self.on_menu_app_options_activate
        app.signals["on_menu_manage_plugins_activate"] = \
            self.on_menu_manage_plugins_activate
        app.signals["on_window_configure_event"] = \
            lambda *args: debounced_save_layout()

        self.builder = gtk.Builder()
        # Read glade file using `pkgutil` to also support loading from `.zip`
        # files (e.g., in app packaged with Py2Exe).
        glade_str = pkgutil.get_data(__name__,
                                     'glade/about_dialog.glade')
        self.builder.add_from_string(glade_str)

        app.main_window_controller = self
        self.protocol_list_view = None

        self.checkbutton_realtime_mode.set_sensitive(False)
        self.button_open_log_directory.set_sensitive(False)
        self.button_open_log_notes.set_sensitive(False)

        if app.config.data.get('advanced_ui', False):
            import IPython

            self.debug_menu_item = gtk.MenuItem('De_bug...')
            self.debug_menu_item.show()
            self.ipython_menu_item = gtk.MenuItem('_IPython...')
            self.ipython_menu_item.show()


            def activate_debugger(parent):
                try:
                    plugin = get_service_instance_by_name(
                        'microdrop.dmf_control_board')
                    control_board = plugin.control_board
                except KeyError:
                    plugin = None
                    control_board = None

                if PUDB_AVAILABLE:
                    pudb.set_trace()
                else:
                    pdb.set_trace()
            self.debug_menu_item.connect('activate', lambda *args:
                                         activate_debugger(self))
            self.ipython_menu_item.connect('activate', lambda *args:
                                           IPython.embed())
            self.menu_tools.append(self.debug_menu_item)
            self.menu_tools.append(self.ipython_menu_item)

    def main(self):
        try:
            gtk.main()
        except KeyboardInterrupt:
            self.shutdown(0)

    def get_text_input(self, title, label, default_value=""):
        self.text_input_dialog.set_title(title)
        self.text_input_dialog.label.set_markup(label)
        self.text_input_dialog.textentry.set_text(default_value)
        self.text_input_dialog.set_transient_for(self.view)
        response = self.text_input_dialog.run()
        self.text_input_dialog.hide()
        name = ""
        if response == gtk.RESPONSE_OK:
            name = self.text_input_dialog.textentry.get_text()
        return name

    @gtk_threadsafe
    def _save_layout(self):
        '''
        .. versionadded:: 2.16

        Save MicroDrop main window size and position.
        '''
        app = get_app()
        data = app.get_app_values()
        allocation = self.view.get_allocation()

        update_required = False
        for key in ('width', 'height'):
            new_value = getattr(allocation, key)
            if data[key] != new_value:
                update_required = True
                data[key] = new_value
        position = dict(zip('xy', self.view.get_position()))
        for key in 'xy':
            if data[key] != position[key]:
                update_required = True
                data[key] = position[key]

        if update_required:
            _L().info('Save window size position to config.')
            app.set_app_values(data)

    def shutdown(self, return_code):
        '''
        .. versionchanged:: 2.15.2
            Process shut down directly (instead of using
            :func:`gobject.idle_add`) if executing in main thread to maintain
            expected behaviour in cases where the GTK main loop is no longer
            running.

        .. versionchanged:: 2.15.2
            Do not explicitly disable ZeroMQ hub.  Since the hub process is
            configured as daemonic, it will automatically exit when the main
            MicroDrop process exits.

        .. versionchanged:: 2.25
            Explicitly stop ZeroMQ asyncio execution event loop (not to be
            confused with the ZeroMQ hub process) __after__ all other plugins
            have processed the `on_app_exit` signal.

        .. versionchanged:: 2.28.1
            Process outstanding GTK events before exiting.
        '''
        logger = _L()  # use logger with method context

        def _threadsafe_shut_down(*args):
            logger.info('Execute `on_app_exit` handlers.')
            emit_signal("on_app_exit")
            logger.info('Quit GTK main loop')
            logger.info('Process outstanding GTK events')
            while gtk.events_pending():
                gtk.main_iteration_do(block=False)
            gtk.main_quit()
            # XXX Other plugins may require the ZeroMQ execution event loop
            # while processing the `on_app_exit` signal. Explicitly stop ZeroMQ
            # execution event loop __after__ all other plugins have processed
            # the `on_app_exit` signal.
            service = get_service_instance_by_name('microdrop.zmq_hub_plugin',
                                                   env='microdrop')
            service.cleanup()
            raise SystemExit(return_code)

        if not self._shutting_down.is_set():
            logger.info('Shutting down')
            self._shutting_down.set()
            if get_app().gtk_thread_active():
                # Process shut down directly if executing in main thread.
                _threadsafe_shut_down()
            else:
                # Try to schedule shut down to run in main thread.
                gobject.idle_add(_threadsafe_shut_down)

    def on_delete_event(self, widget, data=None):
        self.shutdown(0)

    def on_destroy(self, widget, data=None, return_code=0):
        self.shutdown(return_code)

    def on_about(self, widget, data=None):
        '''
        .. versionchanged:: 2.17
            Use :attr:`microdrop.__version__` for MicroDrop version.
        '''
        app = get_app()
        dialog = self.builder.get_object("about_dialog")
        dialog.set_transient_for(app.main_window_controller.view)
        dialog.set_version(__version__)
        dialog.run()
        dialog.hide()

    def on_menu_online_help_activate(self, widget, data=None):
        '''
        .. versionchanged:: 2.27
            Set help URL from ``MICRODROP_HELP_URL`` environment variable (if
            set).
        '''
        help_url = os.environ.get('MICRODROP_HELP_URL',
                                  'https://github.com/wheeler-microfluidics/microdrop/wiki')
        webbrowser.open_new_tab(help_url)

    def on_menu_manage_plugins_activate(self, widget, data=None):
        service = get_service_instance_by_name(
                    'microdrop.gui.plugin_manager_controller', env='microdrop')
        service.dialog.window.set_transient_for(self.view)
        service.dialog.run()

    def on_button_open_log_directory(self, widget, data=None):
        '''
        Open selected experiment log directory in system file browser.
        '''
        app = get_app()
        app.experiment_log.get_log_path().launch()

    def on_button_open_log_notes(self, widget, data=None):
        '''
        Open selected experiment log notes.
        '''
        app = get_app()
        notes_path = app.experiment_log.get_log_path() / 'notes.txt'
        if not notes_path.isfile():
            notes_path.touch()
        notes_path.launch()

    def on_realtime_mode_toggled(self, widget, data=None):
        '''
        .. versionchanged:: 2.15.1
            Prevent toggling from resizing window.
        '''
        app = get_app()
        realtime_mode = self.checkbutton_realtime_mode.get_active()
        app.set_app_values({'realtime_mode': realtime_mode})
        return True

    @gtk_threadsafe
    def on_menu_app_options_activate(self, widget, data=None):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        from app_options_controller import AppOptionsController

        AppOptionsController().run()

    def on_warning(self, record):
        self.warning(record.message)

    def on_error(self, record):
        self.error(record.message)

    def on_critical(self, record):
        self.error(record.message)

    def error(self, message, title="Error"):
        '''
        .. versionchanged:: 2.11.2
            If not called from within main GTK thread, schedule label update to
            run asynchronously in the main GTK loop.
        '''
        def _error():
            dialog = gtk.MessageDialog(self.view,
                                       gtk.DIALOG_DESTROY_WITH_PARENT,
                                       gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                                       message)
            dialog.set_title(title)
            dialog.run()
            dialog.destroy()

        if not get_app().gtk_thread_active():
            gobject.idle_add(_error)
        else:
            _error()

    def warning(self, message, title="Warning"):
        '''
        .. versionchanged:: 2.11.2
            If not called from within main GTK thread, schedule label update to
            run asynchronously in the main GTK loop.
        '''
        def _warning():
            dialog = gtk.MessageDialog(self.view,
                                       gtk.DIALOG_DESTROY_WITH_PARENT,
                                       gtk.MESSAGE_WARNING, gtk.BUTTONS_CLOSE,
                                       message)
            dialog.set_title(title)
            dialog.run()
            dialog.destroy()

        if not get_app().gtk_thread_active():
            gobject.idle_add(_warning)
        else:
            _warning()

    def question(self, message, title=""):
        '''
        .. versionchanged:: 2.11.2
            If not called from within main GTK thread, schedule label update to
            run asynchronously in the main GTK loop.
        '''
        def _question():
            dialog = gtk.MessageDialog(self.view,
                                       gtk.DIALOG_DESTROY_WITH_PARENT,
                                       gtk.MESSAGE_QUESTION,
                                       gtk.BUTTONS_YES_NO, message)
            dialog.set_title(title)
            dialog.run()
            dialog.destroy()

        if not get_app().gtk_thread_active():
            gobject.idle_add(_question)
        else:
            _question()

    def info(self, message, title=""):
        '''
        .. versionchanged:: 2.11.2
            If not called from within main GTK thread, schedule label update to
            run asynchronously in the main GTK loop.
        '''
        def _info():
            dialog = gtk.MessageDialog(self.view,
                                       gtk.DIALOG_DESTROY_WITH_PARENT,
                                       gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE,
                                       message)
            dialog.set_title(title)
            dialog.run()
            dialog.destroy()

        if not get_app().gtk_thread_active():
            gobject.idle_add(_info)
        else:
            _info()

    def on_app_options_changed(self, plugin_name):
        '''
        .. versionchanged:: 2.11.2
            Schedule label update asynchronously to occur in the main GTK loop.
        '''
        app = get_app()
        if plugin_name == app.name:
            data = app.get_data(app.name)
            if 'realtime_mode' in data:
                proxy = proxy_for(self.checkbutton_realtime_mode)
                gobject.idle_add(proxy.set_widget_value, data['realtime_mode'])

    def on_url_clicked(self, widget, data):
        _L().debug("URL clicked: %s" % data)
        webbrowser.open_new_tab(data)

    def get_protocol_string(self, protocol=None):
        if protocol is None:
            protocol = get_app().protocol
        if protocol is None:
            return 'Protocol: None'
        return 'Protocol: %s' % protocol.name

    def update_label(self, label, obj=None, modified=False, get_string=str):
        '''
        .. versionchanged:: 2.11.2
            Schedule label update asynchronously to occur in the main GTK loop.
        '''
        message = get_string(obj)
        if modified:
            message += ' <b>[modified]</b>'
        gobject.idle_add(label.set_markup, wrap_string(message, 60, "\n\t"))

    def update_protocol_name_label(self, obj=None, **kwargs):
        _kwargs = kwargs.copy()
        _kwargs['get_string'] = self.get_protocol_string
        self.update_label(self.label_protocol_name, obj=obj, **_kwargs)

    def on_protocol_swapped(self, old_protocol, protocol):
        self.on_protocol_changed()

    def on_protocol_changed(self):
        app = get_app()
        self.update_protocol_name_label(modified=app.protocol_controller
                                        .modified)

    @gtk_threadsafe
    def on_experiment_log_changed(self, experiment_log):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.button_open_log_directory.set_sensitive(True)
        self.button_open_log_notes.set_sensitive(True)
        if experiment_log:
            self.label_experiment_id.set_text("Experiment: %s (%s)" %
                                              (str(experiment_log
                                                   .experiment_id),
                                               experiment_log.uuid))

    def get_device_string(self, device=None):
        if device is None:
            device = get_app().dmf_device
        if device is None:
            return 'Device: None'
        return 'Device: %s' % device.name

    def update_device_name_label(self, obj=None, **kwargs):
        _kwargs = kwargs.copy()
        _kwargs['get_string'] = self.get_device_string
        self.update_label(self.label_device_name, obj=obj, **_kwargs)

    @gtk_threadsafe
    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.checkbutton_realtime_mode.set_sensitive(True)
        self.update_device_name_label(dmf_device,
                                      modified=get_app().dmf_device_controller
                                      .modified)

    def on_dmf_device_changed(self, dmf_device):
        self.update_device_name_label(modified=True)

    def on_dmf_device_saved(self, dmf_device, device_path):
        self.update_device_name_label(modified=False)

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest(self.name, 'microdrop.app')]
        elif function_name == 'on_protocol_swapped':
            # make sure app reference is updated first
            return [ScheduleRequest('microdrop.app', self.name)]
        return []

    def on_protocol_pause(self):
        '''
        Reset step timer when protocol is stopped.
        '''
        self.reset_step_timeout()

    @asyncio.coroutine
    def on_step_run(self, *args, **kwargs):
        '''
         - Store start time of step.
         - Start periodic timer to update the step time label.

        .. versionchanged:: 2.11.2
            Schedule label update asynchronously to occur in the main GTK loop.

        .. versionchanged:: 2.29
            Convert to coroutine.

        .. versionchanged:: 2.30
            Refactor to match new `IPlugin` interface.
        '''
        # A new step is starting to run.  Reset step timer.
        self.reset_step_timeout()

        app = get_app()
        if app.running:
            self.step_start_time = datetime.utcnow()

            def update_time_label():
                elapsed_time = datetime.utcnow() - self.step_start_time
                self.label_step_time.set_text(str(elapsed_time).split('.')[0])
                return True

            # Update step time label once per second.
            self.step_timeout_id = gtk.timeout_add(1000, update_time_label)

    def reset_step_timeout(self):
        '''
         - Stop periodic callback.
         - Clear step time label.

        .. versionchanged:: 2.11.2
            Schedule label update asynchronously to occur in the main GTK loop.
        '''
        if self.step_timeout_id is not None:
            gobject.source_remove(self.step_timeout_id)
            self.step_timeout_id = None
        gtk_threadsafe(self.label_step_time.set_text)('-')

    @gtk_threadsafe
    def on_mode_changed(self, old_mode, new_mode):
        '''
        .. versionadded:: 2.25

        .. versionchanged:: 2.28.1
            Disable menu and window close button while protocol is running.
        '''
        if new_mode & ~MODE_RUNNING_MASK:
            # Protocol is not running.  Clear step timer label.
            self.reset_step_timeout()

            # Re-enable UI elements.
            ui_state = True
        else:
            # Disable UI elements while running.
            ui_state = False

        self.checkbutton_realtime_mode.props.sensitive = ui_state

        # Window close button.
        self.view.props.deletable = ui_state

        # Enable menu.
        menubar = self.view.get_children()[0].get_children()[0]
        menubar.props.sensitive = ui_state

PluginGlobals.pop_env()
