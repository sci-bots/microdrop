"""
Copyright 2011 Ryan Fobel and Christian Fobel

This file is part of MicroDrop.

MicroDrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

MicroDrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with MicroDrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import threading

from pygtkhelpers.ui.dialogs import open_filechooser
import conda_helpers as ch
import gtk
import gobject

from .. import glade_path
from ..app_context import get_app
from ..gui.plugin_download_dialog import PluginDownloadDialog
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
        builder = gtk.Builder()
        builder.add_from_file(glade_path()
                              .joinpath('plugin_manager_dialog.glade'))
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
            if p.enabled():
                if package_name not in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].append(package_name)
            else:
                if package_name in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].remove(package_name)
        app.config.save()
        if self.controller.restart_required:
            logger.warning('\n'.join(['Plugins and/or dependencies were '
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
        '''
        def _plugin_download_dialog():
            dialog = PluginDownloadDialog()
            response = dialog.run()

            if response == gtk.RESPONSE_OK:
                selected_plugins = dialog.selected_items()
                if not selected_plugins:
                    return

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
                except:
                    logger.info('Error installing plugins.', exc_info=True)
                    return

                if linked:
                    self.controller.restart_required = True

                try:
                    # Display dialog notifying which plugins were installed.
                    dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
                    dialog.set_title('Plugins installed')
                    dialog.props.text = ('Plugin packages installed '
                                         'successfully.')
                    dialog.props.secondary_use_markup = True
                    dialog.props.secondary_text = ('<tt>{}</tt>'
                                                   .format(install_message))
                    dialog.run()
                    dialog.destroy()
                except:
                    logger.info('Error generating plugins install summary.',
                                exc_info=True)
        gobject.idle_add(_plugin_download_dialog)

    def on_button_install_clicked(self, *args, **kwargs):
        archive_path = open_filechooser('Select plugin file',
                                        action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        patterns=['*.tar.bz2'])
        if archive_path is None:
            return True

        return self.controller.install_from_archive(archive_path)

    def on_button_update_all_clicked(self, *args, **kwargs):
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
