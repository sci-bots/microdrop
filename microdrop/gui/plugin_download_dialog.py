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
import json
import logging

from pygtkhelpers.ui.list_select import ListSelectView
from application_repository.plugins.proxy import PluginRepository
import gtk
import mpm.api

from ..app_context import get_app, APP_VERSION
from ..plugin_manager import get_service_instance_by_name
from .. import glade_path


class PluginDownloadDialog(object):
    def __init__(self):
        builder = gtk.Builder()
        builder.add_from_file(glade_path()
                              .joinpath('plugin_download_dialog.glade'))
        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        self.list_select_view = None
        builder.connect_signals(self)

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    @property
    def controller(self):
        service = get_service_instance_by_name('microdrop.gui'
                                               '.plugin_manager_controller',
                                               env='microdrop')
        return service

    def update(self):
        '''
        Update widgets.
        '''
        app = get_app()
        self.clear_plugin_list()
        self.controller.update()

        try:
            available_packages = mpm.api.available_packages()
        except RuntimeError, exception:
            exception_json = json.load(str(exception))
            logging.error('Could not get list of available plugins.\n%s',
                          exception_json['error'])
            return

        # Only plugins with the same *major* version will be returned.
        installed_packages = set([p.get_plugin_info().package_name
                                  for p in self.controller.plugins])
        to_install = set(available_packages).difference(installed_packages)
        if not to_install:
            return None
        self.list_select_view = ListSelectView(sorted(to_install),
                                               'plugin_name')
        self.vbox_plugins.pack_start(self.list_select_view.widget)
        self.vbox_plugins.show_all()
        return True

    def selected_items(self):
        '''
        Returns
        -------
        list
            Currently selected plugin items.
        '''
        return self.list_select_view.selected_items()

    def run(self):
        '''
        Returns
        -------
        gtk._gtk.ResponseType
            If plugins are selected for installation, return `gtk.RESPONSE_OK`.

            Otherwise, return `gtk.RESPONSE_CANCEL`.
        '''
        app = get_app()
        try:
            if self.update() is None:
                logging.warning('All available plugins are already installed')
                return gtk.RESPONSE_CANCEL
        except IOError:
            logging.error('Could not connect to plugin repository at: %s',
                          app.get_app_value('server_url'))
            return gtk.RESPONSE_CANCEL
        response = self.window.run()
        self.window.hide()
        return response
