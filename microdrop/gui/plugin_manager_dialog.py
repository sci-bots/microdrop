import logging
import threading

import conda_helpers as ch
import gtk
import gobject
import pkgutil

from ..app_context import get_app
from ..gui.plugin_download_dialog import PluginDownloadDialog
from ..logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_manager import get_service_instance_by_name


logger = logging.getLogger(__name__)


class PluginManagerDialog(object):
    '''
    List installed plugins with the following action buttons for each plugin:

     - Enable
     - Disable
     - Update
     - **TODO** Uninstall
    '''
    def __init__(self):
        '''
        .. versionchanged:: X.X.X
            Read glade file using ``pkgutil`` to also support loading from
            ``.zip`` files (e.g., in app packaged with Py2Exe).
        '''
        builder = gtk.Builder()
        # Read glade file using `pkgutil` to also support loading from `.zip`
        # files (e.g., in app packaged with Py2Exe).
        glade_str = pkgutil.get_data(__name__,
                                     'glade/plugin_manager_dialog.glade')
        builder.add_from_string(glade_str)

        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        builder.connect_signals(self)

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    @property
    def controller(self):
        plugin_name = 'microdrop.gui.plugin_manager_controller'
        service = get_service_instance_by_name(plugin_name, env='microdrop')
        return service

    def update(self):
        '''
        Update plugin list widget.
        '''
        self.clear_plugin_list()
        self.controller.update()
        for p in self.controller.plugins:
            self.vbox_plugins.pack_start(p.get_widget())

    def run(self):
        '''
        .. versionchanged:: 2.10.3
            Use :func:`plugin_helpers.get_plugin_info` function to retrieve
            package name.

        .. versionchanged:: 2.10.5
            Save Python module names of enabled plugins (**not** Conda package
            names) to ``microdrop.ini`` configuration file.
        '''
        # TODO
        # ----
        #
        #  - [ ] Remove all references to `app`
        #  - [ ] Use `MICRODROP_CONDA_ETC/plugins/enabled` to maintain enabled
        #    plugin references instead of MicroDrop profile `microdrop.ini`
        app = get_app()
        self.update()
        response = self.window.run()
        self.window.hide()
        for p in self.controller.plugins:
            package_name = p.get_plugin_info().package_name
            # Extract importable Python module name from Conda package name.
            #
            # XXX Plugins are currently Python modules, which means that the
            # installed plugin directory must be a valid module name. However,
            # Conda package name conventions may include `.` and `-`
            # characters.
            module_name = package_name.split('.')[-1].replace('-', '_')
            if p.enabled():
                if module_name not in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].append(module_name)
            else:
                if module_name in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].remove(module_name)
        app.config.save()
        if self.controller.restart_required:
            _L().warning('\n'.join(['Plugins and/or dependencies were '
                                    'installed/uninstalled.',
                                    'Program needs to be restarted for '
                                    'changes to take effect.']))
            # Use return code of `5` to signal program should be restarted.
            app.main_window_controller.on_destroy(None, return_code=5)
            return response
        return response

    def on_button_download_clicked(self, *args, **kwargs):
        '''
        Launch download dialog and install selected plugins.

        .. versionchanged:: 2.10.3
            Show dialog with pulsing progress bar while waiting for plugins to
            finish downloading and installing.
        '''
        logger = _L()  # use logger with method context

        def _plugin_download_dialog():
            download_dialog = PluginDownloadDialog()
            response = download_dialog.run()

            if response != gtk.RESPONSE_OK:
                return

            selected_plugins = download_dialog.selected_items()
            if not selected_plugins:
                return

            # Create event to signify download has completed.
            download_complete = threading.Event()

            def _threadsafe_download(download_complete, selected_plugins):
                try:
                    # Attempt install of all selected plugins, where result is
                    # a list of unlinked packages and a list of linked packages
                    # as tuples of the form `(<package name>, <version>,
                    # <channel>)`.
                    unlinked, linked =\
                        (self.controller
                         .download_and_install_plugin(selected_plugins))
                    install_message = ch.format_install_info(unlinked, linked)
                    logger.info('Installed plugins\n%s', install_message)
                except Exception:
                    logger.info('Error installing plugins.', exc_info=True)
                    return
                finally:
                    download_complete.set()

                if linked:
                    self.controller.restart_required = True

                def _update_dialog():
                    dialog.props.text = ('Plugin packages installed '
                                         'successfully.')
                    dialog.props.secondary_use_markup = True
                    dialog.props.secondary_text = ('<tt>{}</tt>'
                                                   .format(install_message))

                gobject.idle_add(_update_dialog)

            def _pulse(download_complete, progress_bar):
                '''
                Show pulsing progress bar to indicate activity.
                '''
                while not download_complete.wait(1. / 16):
                    gobject.idle_add(progress_bar.pulse)

                def _on_complete():
                    progress_bar.set_fraction(1.)
                    progress_bar.hide()
                    # Enable "OK" button and focus it.
                    dialog.action_area.get_children()[1].props.sensitive = True
                    dialog.action_area.get_children()[1].grab_focus()
                gobject.idle_add(_on_complete)

            dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK_CANCEL)
            dialog.set_position(gtk.WIN_POS_MOUSE)
            dialog.props.resizable = True
            progress_bar = gtk.ProgressBar()
            content_area = dialog.get_content_area()
            content_area.pack_start(progress_bar, True, True, 5)
            content_area.show_all()
            # Disable "OK" button until update has completed.
            dialog.action_area.get_children()[1].props.sensitive = False

            # Launch thread to download the selected plugins.
            download_thread = threading.Thread(target=_threadsafe_download,
                                               args=(download_complete,
                                                     selected_plugins))
            download_thread.daemon = True
            download_thread.start()

            # Launch thread to periodically pulse progress bar.
            progress_thread = threading.Thread(target=_pulse,
                                               args=(download_complete,
                                                     progress_bar))
            progress_thread.daemon = True
            progress_thread.start()

            dialog.props.text = ('Installing the following plugins:\n'
                                 '<tt>{}</tt>'
                                 .format('\n'.join([' - {}'.format(name_i)
                                                    for name_i in
                                                    selected_plugins])))
            dialog.props.use_markup = True
            dialog.run()
            dialog.destroy()
        gobject.idle_add(_plugin_download_dialog)

    def on_button_update_all_clicked(self, *args, **kwargs):
        '''
        .. versionchanged:: 2.10.3
            Show dialog with pulsing progress bar while waiting for plugins to
            update.
        '''
        logger = _L()  # use logger with method context

        def _update_all_plugins():
            plugins_updated = self.controller.update_all_plugins()
            self.controller.update_dialog_running.clear()
            if plugins_updated:
                app = get_app()
                logger.warning('\n'.join(['Plugins and/or dependencies were '
                                          'installed/uninstalled.',
                                          'Program needs to be restarted for '
                                          'changes to take effect.']))
                # Use return code of `5` to signal program should be restarted.
                app.main_window_controller.on_destroy(None, return_code=5)
        if not self.controller.update_dialog_running.is_set():
            # Indicate that the update dialog is running to prevent a
            # second update dialog from running at the same time.
            self.controller.update_dialog_running.set()
            gobject.idle_add(_update_all_plugins)
        else:
            gobject.idle_add(logger.error, 'Still busy processing previous '
                             'update request.  Please wait.')


if __name__ == '__main__':
    pm = PluginManagerDialog()
